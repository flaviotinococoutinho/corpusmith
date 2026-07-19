"""Entrypoint do worker Python ISOLADO (`python -m llmwiki.jobs_proc
<manifest.json>`) — ADR-39 §9.

Protocolo v1: manifesto com campos FECHADOS (desconhecido ⇒ exit 2);
eventos NDJSON no stdout (stage.* re-emitidos do handler + result no
fim); o hard kill é do PAI (runtime/procjobs.py) — aqui só SIGTERM
cooperativo. Roda o MESMO handler do registry (nenhuma regra duplicada;
o bundle continua atrás de BundleWriter/Harness). Exit codes: 0 ok ·
2 manifesto inválido · 3 SIGTERM · 5 erro do handler.
"""
from __future__ import annotations
import json
import signal
import sys
import time
from pathlib import Path

PROTOCOL_VERSION = 1
_MANIFEST_FIELDS = {"protocol_version", "job_id", "trace_id", "job_type",
                    "deadline_epoch_ms", "home", "payload"}


def _emit(event: str, data: dict | None = None) -> None:
    print(json.dumps({"event": event, **(data or {})}, ensure_ascii=False),
          flush=True)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("uso: python -m llmwiki.jobs_proc <manifest.json>",
              file=sys.stderr)
        return 2
    try:
        manifest = json.loads(Path(args[0]).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"manifesto ilegível: {e}", file=sys.stderr)
        return 2
    unknown = set(manifest) - _MANIFEST_FIELDS
    if unknown:
        print(f"manifesto com campos desconhecidos (rejeitados): "
              f"{sorted(unknown)}", file=sys.stderr)
        return 2
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        print(f"protocolo {manifest.get('protocol_version')} ≠ "
              f"{PROTOCOL_VERSION}", file=sys.stderr)
        return 2

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(3))
    _emit("worker.started", {"job_id": manifest["job_id"],
                             "job_type": manifest["job_type"],
                             "protocol_version": PROTOCOL_VERSION})

    if manifest["job_type"] == "_sleep":
        # job de smoke/fault-injection (par do selfcheck nativo): dorme
        # em passos com progresso; payload.kill9 simula crash duro
        payload = manifest.get("payload", {})
        import os
        for step in range(int(payload.get("steps", 100))):
            if payload.get("kill9") and step == 2:
                os.kill(os.getpid(), signal.SIGKILL)
            _emit("stage.progress", {"stage": "_sleep", "step": step})
            time.sleep(float(payload.get("step_seconds", 0.1)))
        _emit("result", {"data": {"slept": True}})
        return 0

    from .jobs import REGISTRY
    from .settings import Settings
    handler = REGISTRY.get(manifest["job_type"])
    if handler is None:
        print(f"job_type desconhecido: {manifest['job_type']}",
              file=sys.stderr)
        return 2
    settings = Settings(home=Path(manifest["home"]))

    class _ProcContext:
        """Compatível com JobContext: __call__ emite, cancelled() é
        sempre False (o cancelamento REAL aqui é SIGTERM/kill do pai —
        mais forte que o cooperativo), gov herda orçamento/ledger do
        runtime.db (REL-1 vale também no processo isolado)."""

        def __init__(self):
            from .runtime.db import connect
            from .runtime.governor import Governor
            self.gov = Governor(settings,
                                connect(settings.app_support / "runtime.db"))

        def __call__(self, type: str, data: dict | None = None) -> None:
            _emit(type, data or {})

        @staticmethod
        def cancelled() -> bool:
            return False

    try:
        result = handler(settings, manifest.get("payload", {}),
                         _ProcContext())
    except Exception as e:                          # noqa: BLE001
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        _emit("worker.failed", {"job_id": manifest["job_id"],
                                "reason": str(e)[:500]})
        return 5
    _emit("result", {"data": result if isinstance(result, dict) else {}})
    _emit("worker.completed", {"job_id": manifest["job_id"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
