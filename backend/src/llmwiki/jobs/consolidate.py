"""Adapter do job `consolidate_inbox` (v0.10): lógica em
usecases/consolidate_inbox.py (consolidação por recorrência, CLS)."""
from __future__ import annotations
from ..facades.compiler import CompilerFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    return CompilerFacade(s).consolidate_inbox(notify=notify)
