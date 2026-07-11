"""Fila de jobs persistente sobre runtime.db (Parte V §5.3).

Dedupe por chave (ex.: "review:2026-W27") — reenfileirar o mesmo trabalho
devolve o job existente em vez de duplicar.
"""
from __future__ import annotations
import json
import threading
import time
import uuid
from sqlite3 import Connection


class JobQueue:
    LEASE_SECONDS = 600

    def __init__(self, db: Connection):
        self.db = db
        self._lock = threading.Lock()

    def enqueue(self, type: str, payload: dict, *, priority: int = 5,
                dedupe_key: str | None = None) -> str:
        with self._lock:
            if dedupe_key:
                row = self.db.execute(
                    "SELECT id FROM jobs WHERE dedupe_key=? "
                    "AND state IN ('queued','leased')", (dedupe_key,)).fetchone()
                if row:
                    return row["id"]
            jid = uuid.uuid4().hex[:12]
            self.db.execute(
                "INSERT INTO jobs(id,type,payload,priority,dedupe_key,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (jid, type, json.dumps(payload), priority, dedupe_key,
                 time.time()))
            self.db.commit()
            return jid

    def lease(self) -> dict | None:
        with self._lock:
            now = time.time()
            self.db.execute(
                "UPDATE jobs SET state='queued' WHERE state='leased' "
                "AND leased_until < ?", (now,))
            row = self.db.execute(
                "SELECT * FROM jobs WHERE state='queued' "
                "ORDER BY priority DESC, created_at LIMIT 1").fetchone()
            if not row:
                self.db.commit()
                return None
            self.db.execute(
                "UPDATE jobs SET state='leased', started_at=?, attempts=attempts+1, "
                "leased_until=? WHERE id=?",
                (now, now + self.LEASE_SECONDS, row["id"]))
            self.db.commit()
            job = dict(row)
            job["payload"] = json.loads(job["payload"])
            return job

    def complete(self, job_id: str, result: dict | None = None) -> None:
        with self._lock:
            self.db.execute(
                "UPDATE jobs SET state='done', finished_at=?, result=? WHERE id=?",
                (time.time(), json.dumps(result or {}, default=str), job_id))
            self.db.commit()

    def fail(self, job_id: str, error: str, *, retry: bool = False) -> None:
        with self._lock:
            state = "queued" if retry else "failed"
            self.db.execute(
                "UPDATE jobs SET state=?, finished_at=?, error=? WHERE id=?",
                (state, time.time(), error[:2000], job_id))
            self.db.commit()

    def list(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT id,type,payload,priority,state,attempts,error,created_at,"
            "started_at,finished_at FROM jobs "
            "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            job = dict(r)
            job["payload"] = json.loads(job["payload"] or "{}")
            out.append(job)
        return out

    def pending_count(self) -> int:
        return self.db.execute(
            "SELECT COUNT(*) c FROM jobs WHERE state IN ('queued','leased')"
        ).fetchone()["c"]
