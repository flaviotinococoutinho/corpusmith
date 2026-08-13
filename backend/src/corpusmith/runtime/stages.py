"""Instrumentação por estágio (Fase 0 do plano híbrido, ADR-39).

Relógio MONOTÔNICO por estágio + cardinalidades + pico de RSS, com
overhead ~zero (dois time.monotonic() por estágio; nada de polling).
O perfil viaja NO RESULTADO da operação (ask/index/consolidate) — o
bench o agrega; nada é persistido em banco (decisão ADR-39: perfis são
telemetria efêmera de decisão, não estado).

Declaração completa de cada métrica (unidade, origem, janela,
cardinalidade, propósito decisório): benchmarks/METRICS.md.
"""
from __future__ import annotations
import resource
import time


def _peak_rss_mb() -> float:
    # Linux: ru_maxrss em KiB (macOS seria bytes; documentado no METRICS)
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                 1)


class StageProfile:
    """Coletor de `<prefix>.<stage>_ms` + contadores + metadados de
    proveniência (backend/versão do algoritmo). Uso:

        profile = StageProfile("ask")
        with profile.stage("fts"):
            ...
        profile.count("pages_considered", n)
        result["profile"] = profile.close()
    """

    def __init__(self, prefix: str, *, backend: str = "python",
                 algorithm_version: str = "1"):
        self._prefix = prefix
        self._t0 = time.monotonic()
        self.data: dict[str, float | int | str] = {
            f"{prefix}.backend": backend,
            f"{prefix}.algorithm_version": algorithm_version}

    def stage(self, name: str) -> "_Stage":
        return _Stage(self, f"{self._prefix}.{name}_ms")

    def add_ms(self, name: str, ms: float) -> None:
        key = f"{self._prefix}.{name}_ms"
        self.data[key] = round(float(self.data.get(key, 0.0)) + ms, 3)

    def count(self, name: str, value: int | float) -> None:
        self.data[f"{self._prefix}.{name}"] = value

    def note(self, name: str, value: str) -> None:
        self.data[f"{self._prefix}.{name}"] = value

    def close(self) -> dict:
        self.data[f"{self._prefix}.total_ms"] = round(
            (time.monotonic() - self._t0) * 1000, 3)
        self.data[f"{self._prefix}.peak_rss_mb"] = _peak_rss_mb()
        return self.data


class _Stage:
    def __init__(self, profile: StageProfile, key: str):
        self._profile, self._key = profile, key

    def __enter__(self) -> "_Stage":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, *exc) -> None:
        elapsed = (time.monotonic() - self._t0) * 1000
        data = self._profile.data
        data[self._key] = round(float(data.get(self._key, 0.0)) + elapsed, 3)
