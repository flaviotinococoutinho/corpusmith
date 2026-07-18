"""Ciclo de vida dos threads do runtime (achado da análise do runner):
Worker e Scheduler sombreavam `Thread._stop` com um Event — mas o
CPython usa `_stop()` como MÉTODO interno de `Thread`, e qualquer
`join()` de thread finalizado explodia com "'Event' object is not
callable". Parar e JUNTAR precisa ser sempre seguro (shutdown limpo)."""
from __future__ import annotations
import time
from llmwiki.runtime.db import connect
from llmwiki.runtime.queue import JobQueue
from llmwiki.runtime.scheduler import Scheduler


def test_scheduler_para_e_junta_sem_typeerror(settings):
    db = connect(settings.app_support / "runtime.db")
    sch = Scheduler(JobQueue(db), interval=0.05)
    sch.start()
    time.sleep(0.15)
    sch.stop()
    sch.join(timeout=5)          # explodia: TypeError 'Event' not callable
    assert not sch.is_alive()
    db.close()
