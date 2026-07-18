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
        # `_halt`, não `_stop`: Thread usa `_stop()` como MÉTODO interno —
        # sombreá-lo com um Event quebra `join()` (TypeError)
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.is_set():
            now = time.localtime()
            if now.tm_wday == 0:                       # segunda-feira
                week = time.strftime("%Y-W%W")
                self.queue.enqueue("reflect", {}, priority=6,
                                   dedupe_key=f"reflect:{week}")
                self.queue.enqueue("review_weekly", {}, priority=6,
                                   dedupe_key=f"review:{week}")
                self.queue.enqueue("metacog", {}, priority=5,
                                   dedupe_key=f"metacog:{week}")
            today = time.strftime("%Y-%m-%d")
            self.queue.enqueue("embed", {}, priority=3,
                               dedupe_key=f"embed:{today}")
            self.queue.enqueue("consolidate_inbox", {}, priority=4,
                               dedupe_key=f"consolidate:{today}")
            self._halt.wait(self.interval)
