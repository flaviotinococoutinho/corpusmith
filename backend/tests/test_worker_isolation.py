"""v1.7 (ADR-39 §8/§16) — isolamento de jobs pesados por processo:
hard timeout REAL, cancelamento REAL (kill), crash → estado transitório
recuperável, protocolo com campos fechados. Fault injection nos pontos
mínimos que o runtime atual permite exercitar de fora.
"""
from __future__ import annotations
import json
import time
import pytest
from llmwiki.runtime.procjobs import (WorkerCancelled, WorkerCrashed,
                                      run_in_subprocess, should_isolate)


class _Ctx:
    """JobContext falso: coleta eventos; cancela quando mandarem."""

    def __init__(self):
        self.events: list[tuple[str, dict]] = []
        self._cancel_at: float | None = None
        self.gov = None

    def __call__(self, type, data=None):
        self.events.append((type, data or {}))

    def cancel_after(self, seconds):
        self._cancel_at = time.monotonic() + seconds

    def cancelled(self):
        return self._cancel_at is not None \
            and time.monotonic() > self._cancel_at


def _job(job_type="_sleep", payload=None, jid="j1"):
    return {"id": jid, "type": job_type, "trace_id": "t1",
            "payload": payload or {}}


def test_flag_gates_isolation(settings):
    assert not should_isolate(settings, "index_rebuild")   # default OFF
    original = settings.get
    settings.get = lambda k, d=None: True \
        if k == "compute.process_isolation" else original(k, d)
    assert should_isolate(settings, "index_rebuild")
    assert not should_isolate(settings, "ask")             # leve: nunca
    settings.get = original


def test_subprocess_job_completes_and_streams_events(settings):
    ctx = _Ctx()
    result = run_in_subprocess(
        settings, _job(payload={"steps": 3, "step_seconds": 0.01}), ctx,
        timeout=30)
    assert result == {"data": {"slept": True}} or result == {"slept": True}
    kinds = [k for k, _ in ctx.events]
    assert "worker.started" in kinds
    assert any(k == "stage.progress" for k in kinds)


def test_real_index_rebuild_runs_isolated(settings, kb):
    """O MESMO handler do registry roda no filho — resultado equivalente
    ao caminho em thread (nenhuma regra duplicada)."""
    ctx = _Ctx()
    result = run_in_subprocess(settings, _job("index_rebuild", {}), ctx,
                               timeout=60)
    payload = result.get("data", result)
    assert payload.get("mode") in ("full", "incremental")


def test_hard_timeout_kills_the_process(settings):
    ctx = _Ctx()
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="hard timeout"):
        run_in_subprocess(
            settings, _job(payload={"steps": 200, "step_seconds": 0.1}),
            ctx, timeout=1.0)
    elapsed = time.monotonic() - started
    assert elapsed < 6.0, f"kill demorou {elapsed:.1f}s (grace estourado)"
    assert any(k == "worker.killed" and d.get("reason") == "hard-timeout"
               for k, d in ctx.events)


def test_cancellation_terminates_within_grace(settings):
    ctx = _Ctx()
    ctx.cancel_after(0.3)
    started = time.monotonic()
    with pytest.raises(WorkerCancelled):
        run_in_subprocess(
            settings, _job(payload={"steps": 200, "step_seconds": 0.1}),
            ctx, timeout=60)
    assert time.monotonic() - started < 6.0
    assert any(k == "worker.killed" and d.get("reason") == "cancel"
               for k, d in ctx.events)


def test_sigkill_crash_is_transient_worker_crashed(settings):
    """Processo morre no meio (kill -9 simulado) ⇒ WorkerCrashed, que É
    OSError ⇒ a fila trata como TRANSITÓRIO (retry/lease), nunca perda
    silenciosa."""
    ctx = _Ctx()
    with pytest.raises(WorkerCrashed):
        run_in_subprocess(
            settings, _job(payload={"kill9": True, "steps": 50}), ctx,
            timeout=30)
    assert issubclass(WorkerCrashed, OSError)      # transitório na fila


def test_manifest_rejects_unknown_fields(settings, tmp_path):
    from llmwiki.jobs_proc import main
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "protocol_version": 1, "job_id": "x", "trace_id": "t",
        "job_type": "_sleep", "home": str(settings.home),
        "payload": {}, "campo_inventado": 1}))
    assert main([str(manifest)]) == 2


def test_manifest_rejects_wrong_protocol(settings, tmp_path):
    from llmwiki.jobs_proc import main
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "protocol_version": 99, "job_id": "x", "trace_id": "t",
        "job_type": "_sleep", "home": str(settings.home), "payload": {}}))
    assert main([str(manifest)]) == 2


def test_native_worker_selfcheck_protocol(tmp_path):
    """Worker NATIVO (Rust): manifesto v1 → eventos NDJSON + report.json
    + exit 0; campo desconhecido ⇒ exit 2. Skipa se o binário não foi
    compilado (instalação sem Rust é suportada)."""
    import subprocess
    from pathlib import Path
    binary = Path(__file__).resolve().parents[2] / "native" / "target" \
        / "release" / "llmwiki-native-worker"
    if not binary.exists():
        pytest.skip("worker nativo não compilado")
    out = tmp_path / "out"
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "protocol_version": 1, "job_id": "n1", "trace_id": "t",
        "job_type": "selfcheck", "input": {}, "output_dir": str(out)}))
    proc = subprocess.run([str(binary), str(manifest)],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    events = [json.loads(line) for line in proc.stdout.splitlines()]
    kinds = [e["event"] for e in events]
    assert kinds[0] == "worker.started" and "worker.completed" in kinds
    report = json.loads((out / "report.json").read_text())
    assert report["status"] == "completed"
    assert report["backend"] == "rust"
    assert report["protocol_version"] == 1
    # campo desconhecido ⇒ recusa explícita
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "protocol_version": 1, "job_id": "n2", "trace_id": "t",
        "job_type": "selfcheck", "input": {}, "output_dir": str(out),
        "inventado": True}))
    proc = subprocess.run([str(binary), str(bad)],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 2
