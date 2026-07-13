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
    """Estados (v1.2): queued → leased → done | failed | cancelled |
    retry_scheduled (transitório, backoff) → queued → … → dead_lettered
    (esgotou tentativas). cancel_requested marca leased para
    cancelamento cooperativo. Órfãos (lease vencido) voltam a queued."""

    LEASE_SECONDS = 600
    MAX_ATTEMPTS = 3
    BACKOFF_BASE = 5.0            # 5s · 10s · 20s (+jitter determinístico)

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
            if dedupe_key:
                # chave já usada por job TERMINAL: libera para o novo ciclo
                # (sem isto o INSERT viola a UNIQUE e mata o scheduler)
                self.db.execute(
                    "UPDATE jobs SET dedupe_key = dedupe_key || ':' || id "
                    "WHERE dedupe_key = ? AND state NOT IN "
                    "('queued','leased','retry_scheduled')", (dedupe_key,))
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
            # órfãos (worker morreu com lease vencido) e retries maduros
            self.db.execute(
                "UPDATE jobs SET state='queued' WHERE state='leased' "
                "AND leased_until < ?", (now,))
            self.db.execute(
                "UPDATE jobs SET state='queued' WHERE "
                "state='retry_scheduled' AND leased_until < ?", (now,))
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
            job["attempts"] = row["attempts"] + 1     # reflete o UPDATE
            job["payload"] = json.loads(job["payload"])
            return job

    def complete(self, job_id: str, result: dict | None = None) -> None:
        with self._lock:
            self.db.execute(
                "UPDATE jobs SET state='done', finished_at=?, result=? WHERE id=?",
                (time.time(), json.dumps(result or {}, default=str), job_id))
            self.db.commit()

    def fail(self, job_id: str, error: str, *,
             transient: bool = False) -> str:
        """Erro PERMANENTE ⇒ failed. TRANSITÓRIO ⇒ retry_scheduled com
        backoff exponencial (jitter determinístico pelo id) até
        MAX_ATTEMPTS; depois dead_lettered. Devolve o estado final."""
        with self._lock:
            row = self.db.execute("SELECT attempts FROM jobs WHERE id=?",
                                  (job_id,)).fetchone()
            attempts = row["attempts"] if row else self.MAX_ATTEMPTS
            if not transient:
                state, due = "failed", None
            elif attempts >= self.MAX_ATTEMPTS:
                state, due = "dead_lettered", None
            else:
                jitter = (hash(job_id) % 100) / 100.0
                state = "retry_scheduled"
                due = time.time() + self.BACKOFF_BASE * (2 ** (attempts - 1))                     + jitter
            self.db.execute(
                "UPDATE jobs SET state=?, finished_at=?, error=?, "
                "leased_until=? WHERE id=?",
                (state, time.time(), error[:2000], due, job_id))
            self.db.commit()
            return state

    def cancel(self, job_id: str) -> str:
        """queued/retry_scheduled ⇒ cancelled na hora; leased ⇒
        cancel_requested (cooperativo — o worker honra ao concluir).
        Devolve o estado resultante; KeyError se não cancelável."""
        with self._lock:
            row = self.db.execute("SELECT state FROM jobs WHERE id=?",
                                  (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            if row["state"] in ("queued", "retry_scheduled"):
                new_state = "cancelled"
            elif row["state"] == "leased":
                new_state = "cancel_requested"
            else:
                raise KeyError(f"{job_id}: estado {row['state']} "
                               "não é cancelável")
            self.db.execute(
                "UPDATE jobs SET state=?, error=COALESCE(error,"
                "'cancelado pelo usuário') WHERE id=?", (new_state, job_id))
            self.db.commit()
            return new_state

    def cancel_requested(self, job_id: str) -> bool:
        row = self.db.execute("SELECT state FROM jobs WHERE id=?",
                              (job_id,)).fetchone()
        return bool(row and row["state"] == "cancel_requested")

    def retry_manual(self, job_id: str) -> None:
        """failed/dead_lettered/cancelled ⇒ queued (zera tentativas)."""
        with self._lock:
            moved = self.db.execute(
                "UPDATE jobs SET state='queued', attempts=0, error=NULL, "
                "leased_until=NULL WHERE id=? AND state IN "
                "('failed','dead_lettered','cancelled')", (job_id,)).rowcount
            self.db.commit()
            if not moved:
                raise KeyError(f"{job_id}: não está em estado reexecutável")

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
            "SELECT COUNT(*) c FROM jobs WHERE state IN "
            "('queued','leased','retry_scheduled','cancel_requested')"
        ).fetchone()["c"]
