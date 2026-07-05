"""Agendador interno (Parte V §5.7): enfileira trabalhos recorrentes.

- revisão semanal (segunda-feira) — dedupe por semana ISO
- varredura de embeddings pendentes (diária)
"""
from __future__ import annotations
import threading
import time
from .queue import JobQueue


class Scheduler(threading.Thread):
    def __init__(self, queue: JobQueue, interval: float = 300.0):
        super().__init__(daemon=True, name="llmwiki-scheduler")
        self.queue = queue
        self.interval = interval
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            now = time.localtime()
            if now.tm_wday == 0:                       # segunda-feira
                self.queue.enqueue("review_weekly", {}, priority=6,
                                   dedupe_key=f"review:{time.strftime('%Y-W%W')}")
            self.queue.enqueue("embed", {}, priority=3,
                               dedupe_key=f"embed:{time.strftime('%Y-%m-%d')}")
            self._stop.wait(self.interval)
