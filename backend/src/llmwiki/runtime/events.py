"""Barramento de eventos: persiste em runtime.db e propaga para assinantes
SSE em memória (Parte V §5.5)."""
from __future__ import annotations
import json
import queue as _queue
import threading
import time
from sqlite3 import Connection


class EventBus:
    def __init__(self, db: Connection):
        self.db = db
        self._lock = threading.Lock()
        self._subscribers: list[_queue.Queue] = []

    def emit(self, channel: str, type: str, data: dict | None = None) -> int:
        payload = json.dumps(data or {}, default=str)
        with self._lock:
            cur = self.db.execute(
                "INSERT INTO events(channel,type,data,created_at) VALUES (?,?,?,?)",
                (channel, type, payload, time.time()))
            self.db.commit()
            seq = cur.lastrowid
            event = {"seq": seq, "channel": channel, "type": type,
                     "data": data or {}}
            for q in list(self._subscribers):
                try:
                    q.put_nowait(event)
                except _queue.Full:
                    pass
        return seq

    def subscribe(self) -> _queue.Queue:
        q: _queue.Queue = _queue.Queue(maxsize=500)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: _queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def tail(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT seq,channel,type,data,created_at FROM events "
            "ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
