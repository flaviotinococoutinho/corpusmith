"""Seleção de backend do ComputeKernel (ADR-39).

`compute.backend` ∈ auto|python|rust:
- auto  → Rust quando disponível e compatível; senão Python, com o
          MOTIVO registrado (fallback observável, nunca oculto);
- rust  → exige Rust; sem `compute.allow_fallback` (default true), a
          indisponibilidade vira erro explícito;
- python→ referência, sempre.

O kernel é cacheado por processo; `selection_report()` expõe a decisão
(backend efetivo, pedido, motivo) para doctor/bench/cockpit.
"""
from __future__ import annotations
import threading
from .python_kernel import PythonComputeKernel

_LOCK = threading.Lock()
_KERNEL = None
_REPORT: dict = {}

VALID_BACKENDS = ("auto", "python", "rust")


def _try_rust():
    from .rust_kernel import RustComputeKernel
    return RustComputeKernel()


def get_kernel(settings, *, refresh: bool = False):
    """Kernel efetivo segundo a config. Determinístico por processo
    (cache); `refresh=True` reavalia (testes/config nova)."""
    global _KERNEL, _REPORT
    with _LOCK:
        if _KERNEL is not None and not refresh:
            return _KERNEL
        requested = str(settings.get("compute.backend", "auto")).lower()
        allow_fallback = bool(settings.get("compute.allow_fallback", True))
        if requested not in VALID_BACKENDS:
            requested = "auto"
        reason = ""
        kernel = None
        if requested in ("auto", "rust"):
            try:
                kernel = _try_rust()
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"
                if requested == "rust" and not allow_fallback:
                    _REPORT = {"requested": requested, "effective": None,
                               "fallback_reason": reason}
                    raise RuntimeError(
                        "compute.backend=rust exigido mas indisponível "
                        f"({reason}) e compute.allow_fallback=false") from e
        if kernel is None:
            kernel = PythonComputeKernel()
        _KERNEL = kernel
        _REPORT = {"requested": requested,
                   "effective": kernel.backend_info().name,
                   "fallback_reason": reason}
        return kernel


def selection_report() -> dict:
    with _LOCK:
        return dict(_REPORT)
