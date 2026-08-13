"""Adapter do job `metacog` (v0.18): varredura metacognitiva semanal —
minera hipóteses de ask_context × ask_outcomes; a lógica vive em
usecases/metacognition.py."""
from __future__ import annotations
from ..facades.cognition import CognitionFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    return CognitionFacade(s).observe(notify=notify)
