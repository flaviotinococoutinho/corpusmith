"""Consulta com evidências (v0.6 §5.3).

Resposta SEMPRE ancorada em chunks do índice; se a resposta vier de API e
não tiver `# Citations`, ela é BLOQUEADA (policy.citation_required é
política local — o cockpit mostra o bloqueio, nunca a resposta sem lastro).
Fallback extrativo funciona 100% offline.
"""
from __future__ import annotations
import re
from ..models.router import ModelRouter, ModelUnavailable
from ..retrieval import dense, fts, fusion
from ..settings import Settings

_PROMPT = (
    "Responda à pergunta usando SOMENTE as evidências numeradas abaixo. "
    "Cite cada afirmação com [n]. Termine com uma seção `# Citations` "
    "listando cada [n] usado, no formato `[n] <página>`. Se as evidências "
    "não bastarem, diga o que falta.\n\n"
    "Pergunta: {query}\n\nEvidências:\n{evidence}\n")


def answer(s: Settings, query: str, *, deep: bool = False,
           local_only: bool = False, gov=None) -> dict:
    hits = fts.search(s, query, limit=8)
    router = ModelRouter(s, gov)
    if deep:
        hits = fusion.rrf(hits, dense.search(s, query, router=router), limit=8)

    evidence = [{"page": h["page"], "resource": h.get("resource"),
                 "body": h["text"], "stale": bool(h.get("stale"))}
                for h in hits]
    gaps: list[str] = []
    if not evidence:
        gaps.append("nenhuma evidência indexada para esta consulta "
                    "(rode `okf index` ou compile fontes)")

    numbered = "\n\n".join(
        f"[{i + 1}] ({e['page']}) {e['body'][:800]}"
        for i, e in enumerate(evidence))

    blocked = False
    try:
        privacy = "local_only" if local_only else "api_allowed"
        r = router.complete(_PROMPT.format(query=query, evidence=numbered),
                            privacy=privacy, deep=deep, max_tokens=1024)
        text, via = r["text"], r["via"]
        if via.startswith("api:") and s.policy.get("citation_required", True):
            if not re.search(r"^#{1,2}\s*Citations\s*$", text, re.M):
                blocked = True
    except ModelUnavailable:
        text, via = _extractive(query, evidence), "local:extractive"

    return {"answer": text, "via": via, "blocked": blocked,
            "evidence": evidence, "gaps": gaps}


def _extractive(query: str, evidence: list[dict]) -> str:
    if not evidence:
        return "Sem evidências na base para responder."
    lines = [f"Trechos mais relevantes para: **{query}**\n"]
    for i, e in enumerate(evidence[:5]):
        lines.append(f"[{i + 1}] {e['body'][:400]}\n")
    lines.append("# Citations\n")
    lines += [f"[{i + 1}] {e['page']}" for i, e in enumerate(evidence[:5])]
    return "\n".join(lines)


def run(s: Settings, payload: dict, emit) -> dict:
    return answer(s, payload["query"], deep=payload.get("deep", False),
                  local_only=payload.get("local_only", False))
