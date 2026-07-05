"""Adapter do job `ask` (v0.9): a lógica vive em usecases/ask_memory.py;
aqui só a tradução fila→facade e as entradas programáticas estáveis."""
from __future__ import annotations
from ..facades.memory import MemoryFacade
from ..settings import Settings


def answer(s: Settings, query: str, *, deep: bool = False,
           local_only: bool = False, gov=None,
           as_of: str | None = None) -> dict:
    return MemoryFacade(s, gov).ask(query, deep=deep, local_only=local_only,
                                    as_of=as_of)


def answer_local(s: Settings, query: str, *, as_of: str | None = None,
                 k: int = 5) -> dict:
    """Entrada programática LOCAL-only (sem API) — usada pelo eval_memory."""
    return answer(s, query, local_only=True, as_of=as_of)


def run(s: Settings, payload: dict, emit) -> dict:
    return answer(s, payload["query"], deep=payload.get("deep", False),
                  local_only=payload.get("local_only", False),
                  as_of=payload.get("as_of"))
