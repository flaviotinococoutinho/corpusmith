"""Worker: consome a fila e despacha para o registry de jobs
(Parte V §5.8). Cada job roda com slot da sua classe e emite eventos
job.started / job.done / job.failed no canal "jobs".

v1.4 (REL-2, backlog da auditoria): cada job roda sob um WATCHDOG que
(a) renova o lease periodicamente — HEARTBEAT: um job legítimo passando
de LEASE_SECONDS não é mais tratado como órfão e re-executado em
paralelo; (b) impõe TIMEOUT por classe — estourou, marca cancel_requested.
O `emit` virou um JobContext: além de emitir eventos, expõe `.cancelled()`
— o token de cancelamento COOPERATIVO que handlers longos (pipeline)
consultam em boundaries seguros para parar NO MEIO, não só no fim.
"""
from __future__ import annotations
import threading
import time
import traceback
from ..kernel.identity import factory as id_factory
from ..settings import Settings
from .events import EventBus
from .governor import Governor
from .queue import JobQueue
from .slots import Slots

# tempo de parede máximo por classe de job (segundos). Estourou ⇒
# cancel_requested; handlers cooperativos param no próximo boundary.
JOB_TIMEOUTS = {"lora_train": 3600, "ocr": 1200, "compile_source": 900,
                "consolidate_inbox": 900, "leiden": 600, "pipeline": 1800}
DEFAULT_TIMEOUT = 600
_HEARTBEAT_SECONDS = 30.0


class JobContext:
    """Passado aos handlers no lugar da antiga função `emit`. Chamá-lo
    emite evento (compatível com todo handler existente); `.cancelled()`
    é o token cooperativo; `.gov` é o Governor do daemon (REL-1: jobs
    que chamam modelo herdam orçamento e ledger, nunca criam rota solta)."""

    def __init__(self, bus: EventBus, job_id: str, trace_id: str,
                 queue: JobQueue, gov: Governor | None = None):
        self._bus, self._job_id, self._trace = bus, job_id, trace_id
        self._queue = queue
        self.gov = gov

    def __call__(self, type: str, data: dict | None = None) -> None:
        self._bus.emit("jobs", type,
                       {"id": self._job_id, "trace_id": self._trace,
                        **(data or {})})

    def cancelled(self) -> bool:
        return self._queue.cancel_requested(self._job_id)

    @property
    def job_id(self) -> str:
        return self._job_id


class Worker(threading.Thread):
    def __init__(self, s: Settings, queue: JobQueue, bus: EventBus,
                 gov: Governor, slots: Slots):
        super().__init__(daemon=True, name="llmwiki-worker")
        self.s, self.queue, self.bus, self.gov, self.slots = s, queue, bus, gov, slots
        # `_halt`, não `_stop`: Thread usa `_stop()` como MÉTODO interno —
        # sombreá-lo com um Event quebra `join()` (TypeError)
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def _watchdog(self, job: dict, done: threading.Event) -> None:
        """Heartbeat + timeout enquanto o handler roda."""
        timeout = JOB_TIMEOUTS.get(job["type"], DEFAULT_TIMEOUT)
        started = time.time()
        while not done.wait(_HEARTBEAT_SECONDS):
            self.queue.renew_lease(job["id"])            # heartbeat
            if time.time() - started > timeout:
                try:
                    self.queue.cancel(job["id"])         # pede parada
                except KeyError:
                    pass
                self.bus.emit("jobs", "job.timeout",
                              {"id": job["id"], "type": job["type"],
                               "after_s": round(time.time() - started)})
                return

    def run(self) -> None:
        from ..jobs import REGISTRY
        poll = float(self.s.worker.get("poll_seconds", 1.0))
        while not self._halt.is_set():
            # quiescência de backup (v1.4): com o lock presente, não
            # LEASE novos jobs — o backup captura um instante consistente
            if (self.s.app_support / "backup.lock").exists():
                self._halt.wait(poll)
                continue
            job = self.queue.lease()
            if not job:
                self._halt.wait(poll)
                continue
            handler = REGISTRY.get(job["type"])
            if handler is None:
                self.queue.fail(job["id"], f"job type desconhecido: {job['type']}")
                continue
            trace_id = id_factory("job").next_rendered()
            self.bus.emit("jobs", "job.started",
                          {"id": job["id"], "type": job["type"],
                           "trace_id": trace_id})
            ctx = JobContext(self.bus, job["id"], trace_id, self.queue,
                             gov=self.gov)
            done = threading.Event()
            watch = threading.Thread(target=self._watchdog, args=(job, done),
                                     daemon=True)
            watch.start()
            try:
                from .procjobs import run_in_subprocess, should_isolate
                with self.slots.hold(job["type"]):
                    if should_isolate(self.s, job["type"]):
                        # REL-2b (ADR-39): processo isolado ⇒ hard kill
                        # e timeout REAIS para jobs pesados
                        result = run_in_subprocess(
                            self.s, {**job, "trace_id": trace_id}, ctx,
                            timeout=JOB_TIMEOUTS.get(job["type"],
                                                     DEFAULT_TIMEOUT))
                    else:
                        result = handler(self.s, job["payload"], ctx)
                done.set()
                if self.queue.cancel_requested(job["id"]):
                    # cooperativo: honrado no boundary (handlers longos já
                    # pararam no meio ao ver ctx.cancelled())
                    self.queue.fail(job["id"], "cancelado")
                    self.bus.emit("jobs", "job.cancelled",
                                  {"id": job["id"], "trace_id": trace_id})
                    continue
                self.queue.complete(job["id"], result)
                self.bus.emit("jobs", "job.done",
                              {"id": job["id"], "type": job["type"],
                               "trace_id": trace_id})
            except Exception as e:
                done.set()
                transient = isinstance(e, (TimeoutError, ConnectionError,
                                           InterruptedError, OSError))
                state = self.queue.fail(
                    job["id"], f"{type(e).__name__}: {e}\n"
                    + traceback.format_exc(limit=5), transient=transient)
                self.bus.emit("jobs", f"job.{state}",
                              {"id": job["id"], "type": job["type"],
                               "trace_id": trace_id, "error": str(e)})
