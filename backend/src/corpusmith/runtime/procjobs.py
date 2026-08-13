"""Isolamento de jobs pesados por PROCESSO (REL-2b / ADR-39 §8).

Thread não fornece hard-kill para trabalho síncrono CPU-bound (limitação
registrada no ADR-36). Aqui o handler roda num SUBPROCESSO
(`python -m corpusmith.jobs_proc <manifest>`), e o pai ganha os poderes que
faltavam: CANCELAMENTO real (terminate → grace → kill) e HARD TIMEOUT
real (kill no prazo, sempre). Protocolo v1 do ADR-39 §9: manifesto JSON
com campos fechados; eventos NDJSON no stdout; resultado no evento
final. O worker filho JAMAIS escreve no bundle fora do
BundleWriter/Harness (roda o MESMO handler do registry).

Ligado por `compute.process_isolation` (default False nesta entrega —
porta de entrada pequena; o comportamento em thread permanece o
default documentado).
"""
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import time
from ..settings import Settings

PROTOCOL_VERSION = 1
GRACE_SECONDS = 2.0          # terminate → kill
POLL_SECONDS = 0.1

# classes candidatas a isolamento (espelha slots.HEAVY + manutenção)
ISOLATABLE = {"compile_source", "lora_train", "leiden", "ocr", "pipeline",
              "index_rebuild", "consolidate_inbox", "_sleep"}


def should_isolate(s: Settings, job_type: str) -> bool:
    return bool(s.get("compute.process_isolation", False)) \
        and job_type in ISOLATABLE


class WorkerCrashed(OSError):
    """Processo morreu sem relatório (sinal/crash) — TRANSITÓRIO: o
    lease devolve o job à fila (at-least-once + idempotência)."""


class WorkerCancelled(RuntimeError):
    """Cancelamento honrado com terminate/kill — estado explícito."""


def run_in_subprocess(s: Settings, job: dict, ctx, *,
                      timeout: float) -> dict:
    """Executa o handler do job num subprocesso com deadline DURO.
    Eventos do filho são re-emitidos via ctx; cancelamento cooperativo
    (ctx.cancelled()) vira terminate→kill; timeout vira kill +
    TimeoutError (transitório na fila). Diretório temporário por job,
    limpo pelo chamador do próximo boot se sobrar (crash)."""
    workdir = s.app_support / "proc" / job["id"]
    workdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "job_id": job["id"],
        "trace_id": job.get("trace_id", ""),
        "job_type": job["type"],
        "deadline_epoch_ms": int((time.time() + timeout) * 1000),
        "home": str(s.home),
        "payload": job.get("payload", {}),
    }
    manifest_path = workdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    child = subprocess.Popen(
        [sys.executable, "-m", "corpusmith.jobs_proc", str(manifest_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(workdir))
    os.set_blocking(child.stdout.fileno(), False)
    deadline = time.monotonic() + timeout
    result: dict | None = None
    buffer = ""

    def _pump() -> None:
        nonlocal buffer, result
        try:
            chunk = child.stdout.read()      # binário não-bloqueante
        except (OSError, ValueError):
            return
        if not chunk:
            return
        buffer += chunk.decode("utf-8", errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "result":
                result = event.get("data", {})
            elif event.get("event"):
                ctx(event["event"], {k: v for k, v in event.items()
                                     if k != "event"})

    def _kill(reason: str) -> None:
        child.terminate()
        try:
            child.wait(GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        ctx("worker.killed", {"reason": reason})

    try:
        while True:
            _pump()
            code = child.poll()
            if code is not None:
                break
            if ctx.cancelled():
                _kill("cancel")
                raise WorkerCancelled("cancelado (processo terminado)")
            if time.monotonic() > deadline:
                _kill("hard-timeout")
                raise TimeoutError(
                    f"{job['type']}: hard timeout {timeout:.0f}s "
                    "(processo morto — não só sinalizado)")
            time.sleep(POLL_SECONDS)
        _pump()
    finally:
        if child.stdout:
            child.stdout.close()
    stderr_raw = child.stderr.read() if child.stderr else b""
    stderr_tail = (stderr_raw or b"").decode(
        "utf-8", errors="replace")[-2000:]
    if child.stderr:
        child.stderr.close()
    if child.returncode != 0:
        if child.returncode < 0 or result is None and \
                child.returncode in (-signal.SIGKILL, -signal.SIGTERM, 137):
            raise WorkerCrashed(
                f"{job['type']}: processo morreu (rc={child.returncode}) "
                f"sem relatório — {stderr_tail}")
        raise RuntimeError(
            f"{job['type']}: worker falhou rc={child.returncode} — "
            f"{stderr_tail}")
    if result is None:
        raise WorkerCrashed(
            f"{job['type']}: saiu 0 mas sem evento result — protocolo "
            "violado")
    return result
