"""Consulta com evidências (v0.6 §5.3, estendida na v0.8 §6.2/§7/§9).

A pergunta passa pelo MESMO normalizador da memória (simetria pergunta↔
memória): datas viram filtro temporal (`as_of`), entidades viram um stream
extra na fusão. Overlay do reflect ajusta o ranking; descida hierárquica
gera trajetória visível; sem evidência suficiente o sistema SE ABSTÉM
(LongMemEval) em vez de fabricar resposta. Fallback extrativo 100% offline.
"""
from __future__ import annotations
import re
import time
import uuid
from ..models.router import ModelRouter, ModelUnavailable
from ..normalize import analyze
from ..okf.authorities import load_gazetteer
from ..okf.bundle import BundleReader
from ..retrieval import dense, descend, fts
from ..runtime.db import connect
from ..settings import Settings

_PROMPT = (
    "Responda à pergunta usando SOMENTE as evidências numeradas abaixo. "
    "Cite cada afirmação com [n]. Termine com uma seção `# Citations` "
    "listando cada [n] usado, no formato `[n] <página>`. Se as evidências "
    "não bastarem, diga o que falta.\n\n"
    "Pergunta: {query}\n\nEvidências:\n{evidence}\n")

_GLOBAL_MARKERS = re.compile(
    r"vis[aã]o geral|principais|temas|panorama|overview|resumo geral", re.I)

_RRF_K = 60


def _first_chunks(idx, pages: list[str]) -> list[dict]:
    out = []
    for p in pages:
        row = idx.execute(
            "SELECT id, page, text, resource, privacy, stale, valid_at, "
            "invalid_at FROM chunks WHERE page=? ORDER BY ord LIMIT 1",
            (p,)).fetchone()
        if row:
            out.append(dict(row))
    return out


def _entity_stream(idx, q_entities: set[str]) -> list[dict]:
    rows = idx.execute(
        "SELECT pe.page, SUM(pe.n) FROM page_entities pe "
        "JOIN entities e ON e.id = pe.entity_id "
        f"WHERE e.canonical IN ({','.join('?' * len(q_entities))}) "
        "GROUP BY pe.page ORDER BY 2 DESC LIMIT 20",
        tuple(q_entities)).fetchall()
    return _first_chunks(idx, [p for p, _ in rows])


def _valid_at(hit: dict, as_of: str) -> bool:
    va, ia = hit.get("valid_at"), hit.get("invalid_at")
    return (not va or str(va)[:len(as_of)] <= as_of) and \
           (not ia or str(ia)[:len(as_of)] > as_of)


def answer(s: Settings, query: str, *, deep: bool = False,
           local_only: bool = False, gov=None, as_of: str | None = None) -> dict:
    ask_id = uuid.uuid4().hex[:12]
    kb = s.path("knowledge")
    gaz = load_gazetteer(BundleReader(kb / "bundle"))
    router = ModelRouter(s, gov)
    idx = connect(s.app_support / "index.db")

    # (a) simetria pergunta↔memória: mesmo normalizador
    qrep = analyze(query, gaz=gaz)
    as_of = as_of or next((m.data["iso"] for m in qrep.by_kind("date")
                           if m.confidence != "ambiguous"), None)
    q_entities = {m.canonical for m in qrep.matches
                  if m.kind in ("entity", "standard", "identifier")}

    # (b) streams da fusão RRF
    streams: list[list[dict]] = [fts.search(s, query, limit=8)]
    if deep:
        streams.append(dense.search(s, query, router=router))
    if q_entities:
        streams.append(_entity_stream(idx, q_entities))
    trajectory: list[dict] = []
    if s.flag("retrieval.descend"):
        pages, trajectory = descend.run(idx, query)
        streams.append(_first_chunks(idx, pages))
    # roteamento global (graphrag §7): pergunta panorâmica SEM entidade →
    # prioriza community_summary (map-reduce sobre os sumários)
    global_mode = not q_entities and bool(_GLOBAL_MARKERS.search(query))
    if global_mode:
        comm = [r["page"] for r in idx.execute(
            "SELECT DISTINCT page FROM chunks WHERE page LIKE 'communities/%'")]
        streams.insert(0, _first_chunks(idx, comm[:12]))

    # fusão RRF com score explícito (para overlay + abstenção)
    fused_score: dict[int, float] = {}
    by_id: dict[int, dict] = {}
    for results in streams:
        for rank, r in enumerate(results):
            cid = r["id"]
            fused_score[cid] = fused_score.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            by_id.setdefault(cid, r)

    # (c) overlay do reflect (§8): preferred +15% · contested −20%
    ov = {r["page"]: r["status"] for r in idx.execute(
        "SELECT page, status FROM page_overlay")}
    for cid, hit in by_id.items():
        fused_score[cid] *= {"preferred": 1.15,
                             "contested": 0.8}.get(ov.get(hit["page"]), 1.0)

    ordered = sorted(by_id.values(), key=lambda h: -fused_score[h["id"]])
    # filtro temporal (zep): fora da validade em as_of ⇒ despriorizada
    if as_of:
        ordered = [h for h in ordered if _valid_at(h, as_of)] \
                + [h for h in ordered if not _valid_at(h, as_of)]
    hits = ordered[:8]
    idx.close()

    evidence = [{"page": h["page"], "resource": h.get("resource"),
                 "body": h["text"], "stale": bool(h.get("stale"))}
                for h in hits]

    # (d) ABSTENÇÃO (LongMemEval): sem evidência, não fabricar resposta
    top = fused_score.get(hits[0]["id"], 0.0) if hits else 0.0
    if not hits or top < float(s.get("ask.abstain_threshold", 0.0)):
        return {"answer": None, "abstained": True, "blocked": False,
                "via": "none", "ask_id": ask_id,
                "gaps": [f"sem cobertura para: {query}"],
                "evidence": [], "as_of": as_of, "trajectory": trajectory}

    # heat: leitura conta (alimenta o reflect, §8)
    rt = connect(s.app_support / "runtime.db")
    now = time.time()
    for page in {e["page"] for e in evidence}:
        rt.execute("INSERT INTO page_heat(path, reads, last_seen) VALUES (?,1,?) "
                   "ON CONFLICT(path) DO UPDATE SET reads = reads + 1, "
                   "last_seen = ?", (page, now, now))
    rt.commit()
    rt.close()

    numbered = "\n\n".join(
        f"[{i + 1}] ({e['page']}) {e['body'][:800]}"
        for i, e in enumerate(evidence))
    gaps: list[str] = []

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
            "abstained": False, "ask_id": ask_id,
            "evidence": evidence, "gaps": gaps,
            "as_of": as_of, "trajectory": trajectory}


def answer_local(s: Settings, query: str, *, as_of: str | None = None,
                 k: int = 5) -> dict:
    """Entrada programática LOCAL-only (sem API) — usada pelo eval_memory."""
    return answer(s, query, local_only=True, as_of=as_of)


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
                  local_only=payload.get("local_only", False),
                  as_of=payload.get("as_of"))
