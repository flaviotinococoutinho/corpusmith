"""Job `rerank` (Parte V §7.3): reordenação profunda de candidatos.
Implementação local-first: heurística de sobreposição de termos; um
cross-encoder local pode substituir `score()` sem mudar o contrato."""
from __future__ import annotations
import re
from ..settings import Settings


def score(query: str, text: str) -> float:
    q = set(re.findall(r"\w+", query.lower()))
    t = set(re.findall(r"\w+", text.lower()))
    return len(q & t) / (len(q) or 1)


def rerank(query: str, candidates: list[dict], limit: int = 8) -> list[dict]:
    return sorted(candidates, key=lambda c: -score(query, c["text"]))[:limit]


def run(s: Settings, payload: dict, emit) -> dict:
    out = rerank(payload["query"], payload.get("candidates", []),
                 payload.get("limit", 8))
    return {"results": out}
