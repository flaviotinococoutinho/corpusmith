"""Adapter do job `eval_memory` (v0.9): lógica em usecases/evaluate_memory.

Mora em `jobs/` desde o ADR-60: em `harness/` ele era a única aresta
`harness → facades` do repositório — um adapter de job dentro do domínio
canônico, apontando para fora do gradiente (`architecture.toml [[tier]]`).
O `ontology lint` dos blocos do projeto foi o que a acusou."""
from __future__ import annotations
from ..facades.memory import MemoryFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    return MemoryFacade(s).evaluate(notify=notify)
