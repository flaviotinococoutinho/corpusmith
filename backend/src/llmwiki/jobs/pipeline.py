"""Adapter do job `pipeline` (v0.17): a orquestração vive em
usecases/run_pipeline.py; aqui só a tradução fila→facade E a injeção do
REGISTRY real (import tardio para não ciclar com jobs/__init__)."""
from __future__ import annotations
from ..facades.compiler import CompilerFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    from . import REGISTRY

    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    # token cooperativo (v1.4): o worker passa um JobContext com
    # .cancelled(); repassamos ao RunPipeline p/ parada entre estágios
    cancelled = getattr(emit, "cancelled", None)
    return CompilerFacade(s).run_pipeline(payload["name"], REGISTRY,
                                          notify=notify, cancelled=cancelled)
