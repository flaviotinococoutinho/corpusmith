"""Adapter do job `leiden` (v0.9): lógica em usecases/detect_communities.py
(comunidades + pontes topológicas + páginas community_summary)."""
from __future__ import annotations
from ..facades.compiler import CompilerFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    # REL-1: o Governor viaja no JobContext (getattr: testes passam função nua)
    return CompilerFacade(s, gov=getattr(emit, "gov", None)) \
        .detect_communities(notify=notify)
