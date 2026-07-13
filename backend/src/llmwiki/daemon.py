"""Daemon local (Parte V §5.10): fila + worker + scheduler + API HTTP.

Sobe em 127.0.0.1 com token efêmero (handshake em app_support/daemon.json,
lido pelo Electron/CLI). Bootstrap do knowledge base é idempotente.
"""
from __future__ import annotations
import logging
import uvicorn
from .api.system import build_app, issue_token
from .okf.bootstrap import ensure_bundle
from .runtime.db import connect
from .runtime.events import EventBus
from .runtime.governor import Governor
from .runtime.queue import JobQueue
from .runtime.scheduler import Scheduler
from .runtime.slots import Slots
from .runtime.worker import Worker
from .settings import Settings

log = logging.getLogger("llmwiki")


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    s = Settings.load()
    ensure_bundle(s.path("knowledge"))

    rt = connect(s.app_support / "runtime.db")
    connect(s.app_support / "index.db").close()   # aplica schema do índice

    queue = JobQueue(rt)
    bus = EventBus(rt)
    gov = Governor(s, rt)
    slots = Slots(int(s.worker.get("heavy_slots", 1)),
                  int(s.worker.get("light_slots", 2)))

    recovered = queue.recover_orphans()      # REL-3: órfãos do último crash
    if recovered:
        bus.emit("jobs", "orphans.recovered", {"count": recovered})
    worker = Worker(s, queue, bus, gov, slots)
    worker.start()
    scheduler = Scheduler(queue)
    scheduler.start()

    token = issue_token(s)
    app = build_app(s, queue, gov, bus, token)
    bus.emit("system", "daemon.started", {"version": "0.7.0"})
    log.info("llmwiki daemon em http://%s:%s",
             s.server.get("host"), s.server.get("port"))
    try:
        uvicorn.run(app, host=s.server.get("host", "127.0.0.1"),
                    port=int(s.server.get("port", 8377)), log_level="warning")
    finally:
        worker.stop()
        scheduler.stop()


if __name__ == "__main__":
    main()
