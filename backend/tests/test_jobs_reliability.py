"""v1.2 (Frente D) — máquina de estados de jobs: cancelamento,
retry com backoff, dead-letter, órfãos e retry manual."""
from __future__ import annotations
import time
import pytest
from llmwiki.runtime.db import connect
from llmwiki.runtime.queue import JobQueue


@pytest.fixture
def queue(settings):
    return JobQueue(connect(settings.app_support / "runtime.db"))


def test_cancel_queued_is_immediate(queue):
    jid = queue.enqueue("compile_source", {"path": "x"})
    assert queue.cancel(jid) == "cancelled"
    assert queue.lease() is None                  # não é entregue ao worker


def test_cancel_leased_is_cooperative(queue):
    jid = queue.enqueue("compile_source", {"path": "x"})
    assert queue.lease()["id"] == jid
    assert queue.cancel(jid) == "cancel_requested"
    assert queue.cancel_requested(jid) is True
    with pytest.raises(KeyError):                 # done não é cancelável
        queue.complete(jid)
        queue.cancel(jid)


def test_transient_failure_schedules_backoff_then_dead_letters(queue):
    jid = queue.enqueue("embed", {})
    states = []
    for _ in range(JobQueue.MAX_ATTEMPTS):
        job = queue.lease()
        if job is None:                           # backoff ainda não venceu
            rt = queue.db
            rt.execute("UPDATE jobs SET leased_until = 0 WHERE id=?", (jid,))
            rt.commit()
            job = queue.lease()
        assert job["id"] == jid
        states.append(queue.fail(jid, "rede caiu", transient=True))
    assert states[:-1] == ["retry_scheduled"] * (JobQueue.MAX_ATTEMPTS - 1)
    assert states[-1] == "dead_lettered"          # esgotou tentativas
    # backoff cresce: 5s → 10s (registrado em leased_until)
    assert queue.lease() is None


def test_permanent_failure_never_retries(queue):
    jid = queue.enqueue("embed", {})
    queue.lease()
    assert queue.fail(jid, "payload inválido", transient=False) == "failed"
    assert queue.lease() is None


def test_orphaned_lease_is_recovered(queue):
    jid = queue.enqueue("embed", {})
    queue.lease()                                  # worker "morre"
    queue.db.execute("UPDATE jobs SET leased_until = ? WHERE id=?",
                     (time.time() - 1, jid))
    queue.db.commit()
    recovered = queue.lease()                      # próximo poll resgata
    assert recovered["id"] == jid and recovered["attempts"] == 2


def test_manual_retry_resets_dead_lettered(queue):
    jid = queue.enqueue("embed", {})
    for _ in range(JobQueue.MAX_ATTEMPTS):
        queue.db.execute("UPDATE jobs SET leased_until=0, state='queued' "
                         "WHERE id=? AND state='retry_scheduled'", (jid,))
        queue.db.commit()
        queue.lease()
        queue.fail(jid, "x", transient=True)
    queue.retry_manual(jid)
    job = queue.lease()
    assert job["id"] == jid and job["attempts"] == 1
    with pytest.raises(KeyError):
        queue.retry_manual(jid)                    # leased não é reexecutável


def test_renew_lease_is_heartbeat(queue):
    jid = queue.enqueue("compile_source", {"path": "x"})
    queue.lease()
    before = queue.db.execute("SELECT leased_until FROM jobs WHERE id=?",
                              (jid,)).fetchone()["leased_until"]
    import time as _t; _t.sleep(0.01)
    queue.renew_lease(jid)
    after = queue.db.execute("SELECT leased_until FROM jobs WHERE id=?",
                             (jid,)).fetchone()["leased_until"]
    assert after > before                          # lease estendido


def test_startup_sweep_recovers_leased_and_cancel_requested(queue):
    a = queue.enqueue("embed", {})
    b = queue.enqueue("embed", {})
    queue.lease(); queue.lease()                    # ambos leased
    queue.cancel(b)                                 # b → cancel_requested
    recovered = queue.recover_orphans()
    assert recovered == 2
    leased = queue.db.execute(
        "SELECT COUNT(*) c FROM jobs WHERE state='queued'").fetchone()["c"]
    assert leased == 2                              # ambos de volta à fila


def test_pipeline_cooperative_cancel_stops_between_stages(settings, kb):
    from llmwiki.usecases.run_pipeline import RunPipeline, SavePipeline
    ran = []
    registry = {"a": lambda s, p, e: ran.append("a") or {},
                "b": lambda s, p, e: ran.append("b") or {}}
    SavePipeline(settings, "longo",
                 {"stages": [{"job": "a"}, {"job": "b"}]}).execute()
    # cancela ANTES do 2º estágio (token vira True após o 1º)
    flag = {"n": 0}
    def cancelled():
        flag["n"] += 1
        return flag["n"] > 1                        # True a partir da 2ª checagem
    result = RunPipeline(settings, "longo", registry,
                         cancelled=cancelled).execute()
    assert result["state"] == "cancelled"
    assert ran == ["a"]                             # b NÃO rodou
