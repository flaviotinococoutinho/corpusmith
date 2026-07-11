"""AskMemory — consulta com evidências (v0.9, sobre a v0.8 §6.2).

Melhorias de coordenação sobre o fluxo anterior:
- streams fundidos via EvidenceStreams com CRÉDITO Hedge lido de
  stream_weights (os desfechos do usuário treinam a fusão);
- stream de entidades ponderado por SURPRISAL (−log p): entidade rara
  numa base grande vale mais que a onipresente (IDF na roupa original);
- resposta carrega `uncertainty` (entropia normalizada da distribuição
  fundida) — o Cockpit pode exibir "resposta incerta" mesmo sem abster;
- proveniência página→stream persistida em ask_provenance, fechando o
  laço de aprendizado do RecordOutcome.
"""
from __future__ import annotations
import re
import time
from collections import defaultdict
from .base import UseCase
from ..kernel.graphwalk import personalized_pagerank
from ..kernel.identity import factory as id_factory, parse as parse_id
from ..kernel.information import surprisal
from ..models.router import ModelRouter, ModelUnavailable
from ..normalize import analyze
from ..okf.authorities import load_gazetteer
from ..okf.bundle import BundleReader
from ..retrieval import dense, descend, fts
from ..retrieval.streams import EvidenceStreams
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


class AskMemory(UseCase):
    def __init__(self, settings: Settings, query: str, *, deep: bool = False,
                 local_only: bool = False, gov=None, as_of: str | None = None,
                 _recycled: bool = False):
        self._settings = settings
        self._query = query
        self._deep = deep
        self._local_only = local_only
        self._as_of = as_of
        self._gov = gov
        self._already_recycled = _recycled
        self._router = ModelRouter(settings, gov)

    def _cold_fallback(self, ask_id, fused, as_of, trajectory) -> dict:
        """Abstenção consulta a BASE FRIA (v0.12): memórias congeladas que
        casam com a pergunta viram cold_matches — e, com memory.auto_recycle,
        a melhor é reidratada e a consulta roda de novo (uma única vez)."""
        from .cold_memory import RecycleMemory, cold_search
        matches = cold_search(self._settings, self._query)
        if matches and not self._already_recycled \
                and self._settings.get("memory.auto_recycle", False):
            RecycleMemory(self._settings, matches[0]["page"]).execute()
            return AskMemory(self._settings, self._query, deep=self._deep,
                             local_only=self._local_only, gov=self._gov,
                             as_of=self._as_of, _recycled=True).execute()
        gaps = [f"sem cobertura para: {self._query}"]
        if matches:
            gaps.append("há memória FRIA compatível — recicle para responder: "
                        + ", ".join(m["page"] for m in matches[:3]))
        return {"answer": None, "abstained": True, "blocked": False,
                "via": "none", "ask_id": ask_id,
                "uncertainty": fused.uncertainty, "gaps": gaps,
                "cold_matches": matches,
                "evidence": [], "as_of": as_of, "trajectory": trajectory}

    def execute(self) -> dict:
        # ask_id É o trace id (v0.16): snowflake com módulo=ask e
        # algoritmo=rrf — quem tiver só o id recupera quando/quem/como
        ask_id = id_factory("ask", "rrf").next_rendered()
        kb = self._settings.path("knowledge")
        gazetteer = load_gazetteer(BundleReader(kb / "bundle"))
        idx = connect(self._settings.app_support / "index.db")

        question = analyze(self._query, gaz=gazetteer)
        as_of = self._as_of or next(
            (m.data["iso"] for m in question.by_kind("date")
             if m.confidence != "ambiguous"), None)
        question_entities = {m.canonical for m in question.matches
                             if m.kind in ("entity", "standard", "identifier")}

        streams = EvidenceStreams(credit=self._stream_credit())
        if not question_entities and _GLOBAL_MARKERS.search(self._query):
            communities = [r["page"] for r in idx.execute(
                "SELECT DISTINCT page FROM chunks "
                "WHERE page LIKE 'communities/%'")]
            streams.add("global", self._first_chunks(idx, communities[:12]))
        streams.add("fts", fts.search(self._settings, self._query, limit=8))
        if self._deep:
            streams.add("dense", dense.search(self._settings, self._query,
                                              router=self._router))
        if question_entities:
            seed_weights = self._entity_page_weights(idx, question_entities)
            ranked = sorted(seed_weights, key=lambda p: -seed_weights[p])[:20]
            streams.add("entity", self._first_chunks(idx, ranked))
            # HippoRAG (v0.13): PPR semeado pelas páginas-entidade — alcança
            # fatos a UM OU MAIS saltos de link da pergunta (associatividade)
            streams.add("graph", self._graph_stream(idx, seed_weights))
        trajectory: list[dict] = []
        if self._settings.flag("retrieval.descend"):
            pages, trajectory = descend.run(idx, self._query)
            streams.add("descend", self._first_chunks(idx, pages))

        overlay = {r["page"]: r["status"] for r in idx.execute(
            "SELECT page, status FROM page_overlay")}
        fused = streams.fuse(overlay=overlay, as_of=as_of, limit=8)
        idx.close()

        threshold = float(self._settings.get("ask.abstain_threshold", 0.0))
        if fused.is_empty() or fused.top_score < threshold:
            return self._cold_fallback(ask_id, fused, as_of, trajectory)

        self._record_usage(ask_id, fused)
        evidence = [{"page": h["page"], "resource": h.get("resource"),
                     "body": h["text"], "stale": bool(h.get("stale"))}
                    for h in fused.hits]
        answer, via, blocked = self._compose(evidence)
        return {"answer": answer, "via": via, "blocked": blocked,
                "abstained": False, "ask_id": ask_id,
                "identity": parse_id(ask_id),
                "uncertainty": fused.uncertainty,
                "evidence": evidence, "gaps": [],
                "as_of": as_of, "trajectory": trajectory}

    # ------------------------------------------------------------ streams
    def _stream_credit(self) -> dict[str, float]:
        rt = connect(self._settings.app_support / "runtime.db")
        credit = {r["stream"]: r["weight"] for r in
                  rt.execute("SELECT stream, weight FROM stream_weights")}
        rt.close()
        return credit

    def _entity_page_weights(self, idx,
                             entities: set[str]) -> dict[str, float]:
        """Peso por página = Σ n·surprisal das entidades da pergunta.
        Suavização add-one no corpus: entidade presente em TODAS as páginas
        nunca zera (senão não semearia o PPR em bases pequenas)."""
        corpus = idx.execute(
            "SELECT COUNT(DISTINCT page) c FROM page_entities").fetchone()["c"]
        weights: dict[str, float] = {}
        for entity in entities:
            rows = idx.execute(
                "SELECT pe.page, pe.n FROM page_entities pe "
                "JOIN entities e ON e.id = pe.entity_id "
                "WHERE e.canonical = ?", (entity,)).fetchall()
            information = surprisal(len({r["page"] for r in rows}),
                                    max(corpus, 1) + 1)
            for row in rows:
                weights[row["page"]] = weights.get(row["page"], 0.0) \
                    + row["n"] * information
        return weights

    _EDGE_WEIGHT = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}

    def _graph_stream(self, idx, seeds: dict[str, float]) -> list[dict]:
        if not seeds:
            return []
        adjacency: dict[str, dict[str, float]] = defaultdict(dict)
        for src, dst, conf in idx.execute(
                "SELECT src, dst, COALESCE(confidence,'extracted') "
                "FROM graph_edges"):
            weight = self._EDGE_WEIGHT.get(conf, 0.5)
            adjacency[src][dst] = adjacency[src].get(dst, 0.0) + weight
            adjacency[dst][src] = adjacency[dst].get(src, 0.0) + weight
        if not adjacency:
            return []
        rank = personalized_pagerank(adjacency, seeds)
        top = sorted(rank, key=lambda p: -rank[p])[:12]
        return self._first_chunks(idx, top)

    @staticmethod
    def _first_chunks(idx, pages: list[str]) -> list[dict]:
        out = []
        for page in pages:
            row = idx.execute(
                "SELECT id, page, text, resource, privacy, stale, valid_at, "
                "invalid_at FROM chunks WHERE page=? ORDER BY ord LIMIT 1",
                (page,)).fetchone()
            if row:
                out.append(dict(row))
        return out

    # ---------------------------------------------------------- pós-fusão
    def _record_usage(self, ask_id: str, fused) -> None:
        rt = connect(self._settings.app_support / "runtime.db")
        now = time.time()
        for page, sources in fused.provenance.items():
            rt.execute("INSERT INTO page_heat(path, reads, last_seen, first_seen) "
                       "VALUES (?,1,?,?) ON CONFLICT(path) DO UPDATE SET "
                       "reads = reads + 1, last_seen = ?, "
                       "first_seen = COALESCE(first_seen, ?)",
                       (page, now, now, now, now))
            for stream in sources:
                rt.execute("INSERT OR IGNORE INTO ask_provenance"
                           "(ask_id, page, stream) VALUES (?,?,?)",
                           (ask_id, page, stream))
        rt.commit()
        rt.close()

    def _compose(self, evidence: list[dict]) -> tuple[str, str, bool]:
        numbered = "\n\n".join(
            f"[{i + 1}] ({e['page']}) {e['body'][:800]}"
            for i, e in enumerate(evidence))
        try:
            privacy = "local_only" if self._local_only else "api_allowed"
            r = self._router.complete(
                _PROMPT.format(query=self._query, evidence=numbered),
                privacy=privacy, deep=self._deep, max_tokens=1024)
            text, via = r["text"], r["via"]
            blocked = (via.startswith("api:")
                       and self._settings.policy.get("citation_required", True)
                       and not re.search(r"^#{1,2}\s*Citations\s*$", text, re.M))
            return text, via, blocked
        except ModelUnavailable:
            return self._extractive(evidence), "local:extractive", False

    def _extractive(self, evidence: list[dict]) -> str:
        lines = [f"Trechos mais relevantes para: **{self._query}**\n"]
        for i, e in enumerate(evidence[:5]):
            lines.append(f"[{i + 1}] {e['body'][:400]}\n")
        lines.append("# Citations\n")
        lines += [f"[{i + 1}] {e['page']}" for i, e in enumerate(evidence[:5])]
        return "\n".join(lines)
