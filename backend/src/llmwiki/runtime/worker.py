"""Worker: consome a fila e despacha para o registry de jobs
(Parte V §5.8). Cada job roda com slot da sua classe e emite eventos
job.started / job.done / job.failed no canal "jobs"."""
from __future__ import annotations
import threading
import traceback
from ..kernel.identity import factory as id_factory
from ..settings import Settings
from .events import EventBus
from .governor import Governor
from .queue import JobQueue
from .slots import Slots


class Worker(threading.Thread):
    def __init__(self, s: Settings, queue: JobQueue, bus: EventBus,
                 gov: Governor, slots: Slots):
        super().__init__(daemon=True, name="llmwiki-worker")
        self.s, self.queue, self.bus, self.gov, self.slots = s, queue, bus, gov, slots
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        from ..jobs import REGISTRY
        poll = float(self.s.worker.get("poll_seconds", 1.0))
        while not self._stop.is_set():
            job = self.queue.lease()
            if not job:
                self._stop.wait(poll)
                continue
            handler = REGISTRY.get(job["type"])
            if handler is None:
                self.queue.fail(job["id"], f"job type desconhecido: {job['type']}")
                continue
            # trace da EXECUÇÃO (v0.16): eventos emitidos pelo job herdam
            # o mesmo trace_id — identidade ponta a ponta no /events
            trace_id = id_factory("job").next_rendered()
            self.bus.emit("jobs", "job.started",
                          {"id": job["id"], "type": job["type"],
                           "trace_id": trace_id})

            def emit(type: str, data: dict | None = None,
                     _jid=job["id"], _trace=trace_id):
                self.bus.emit("jobs", type,
                              {"id": _jid, "trace_id": _trace, **(data or {})})

            try:
                with self.slots.hold(job["type"]):
                    result = handler(self.s, job["payload"], emit)
                self.queue.complete(job["id"], result)
                self.bus.emit("jobs", "job.done",
                              {"id": job["id"], "type": job["type"],
                               "trace_id": trace_id})
            except Exception as e:
                self.queue.fail(job["id"], f"{type(e).__name__}: {e}\n"
                                + traceback.format_exc(limit=5))
                self.bus.emit("jobs", "job.failed",
                              {"id": job["id"], "type": job["type"],
                               "trace_id": trace_id, "error": str(e)})
