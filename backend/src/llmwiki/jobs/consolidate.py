"""Adapter do job `consolidate_inbox` (v0.10): lógica em
usecases/consolidate_inbox.py (consolidação por recorrência, CLS)."""
from __future__ import annotations
from ..facades.compiler import CompilerFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    # REL-1: o Governor viaja no JobContext (getattr: testes passam função nua)
    return CompilerFacade(s, gov=getattr(emit, "gov", None)) \
        .consolidate_inbox(notify=notify)
