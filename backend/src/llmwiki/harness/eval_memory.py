"""Adapter do job `eval_memory` (v0.9): lógica em usecases/evaluate_memory."""
from __future__ import annotations
from ..facades.memory import MemoryFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    return MemoryFacade(s).evaluate(notify=notify)
