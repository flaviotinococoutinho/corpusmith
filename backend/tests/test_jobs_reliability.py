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
