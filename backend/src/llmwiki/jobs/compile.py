"""Adapter do job `compile_source` (v0.9): a lógica vive em
usecases/compile_source.py (subclasse do Template Method de página de
máquina); aqui só a tradução fila→facade."""
from __future__ import annotations
from ..facades.compiler import CompilerFacade
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    return CompilerFacade(s).compile(payload["path"], notify=notify)
