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
import heapq
import random
import re
import time
from .base import UseCase
from .cognitive_state import STRATEGIES, current_state, delivery_budget
from ..compute import get_kernel
from ..kernel.identity import factory as id_factory, parse as parse_id
from ..kernel.information import surprisal
from ..models.router import ModelRouter, ModelUnavailable
from ..normalize import analyze
from ..okf.authorities import load_gazetteer
from ..okf.bundle import BundleReader
from ..retrieval import dense, descend, fts
from ..retrieval.streams import EvidenceStreams
from ..runtime.db import connect
from ..runtime.stages import StageProfile
from ..settings import Settings

_PROMPT = (
    "Responda à pergunta usando SOMENTE as evidências numeradas abaixo. "
    "Cite cada afirmação com [n]. Termine com uma seção `# Citations` "
    "listando cada [n] usado, no formato `[n] <página>`. Se as evidências "
    "não bastarem, diga o que falta.\n\n"
    "Pergunta: {query}\n\nEvidências:\n{evidence}\n")

_GLOBAL_MARKERS = re.compile(
    r"vis[aã]o geral|principais|temas|panorama|overview|resumo geral", re.I)

# Resposta adaptativa (v0.18): estratégias de explicação são os EXPERTS
# de um segundo Hedge (o primeiro pesa streams; este pesa COMO explicar).
# Perfil declarado (profile.preferred_strategy) vence o observado.
_STRATEGY_HINT = {
    "direta": "Responda direto ao ponto, sem preâmbulo.",
    "analogia-primeiro": "Abra com UMA analogia fiel (declarando o limite "
                         "dela) e só então a explicação técnica.",
    "exemplo-primeiro": "Abra com um exemplo concreto tirado das "
                        "evidências e generalize a partir dele.",
    "teoria-primeiro": "Apresente primeiro o princípio geral e depois "
                       "desça ao caso concreto.",
    "decomposicao": "Decomponha a resposta em partes pequenas e "
                    "explícitas, uma por vez.",
}


# QA-3 (v1.6.2): [n] de 1–2 dígitos é citação; [2024] é ano e `](` é
# link markdown — precisão > recall: só flagra o que é claramente citação.
_CITATION = re.compile(r"\[(\d{1,2})\](?!\()")


def _invalid_citations(text: str, n_evidence: int) -> list[int]:
    """Números citados fora de 1..n_evidence — proveniência fabricada."""
    cited = {int(m) for m in _CITATION.findall(text)}
    return sorted(n for n in cited if n < 1 or n > n_evidence)


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
        # instrumentação por estágio (Fase 0, ADR-39): monotônico + counts
        self._kernel = get_kernel(self._settings)
        profile = StageProfile("ask", backend=self._kernel.backend_info().name)
        # §19 (ADR-39): UMA conexão runtime.db por consulta — antes eram
        # três (estratégia, crédito e usage abriam/fechavam cada um a sua)
        rt = connect(self._settings.app_support / "runtime.db")
        try:
            # camada cognitiva (v0.18): estado declarado + estratégia
            self._state = current_state(self._settings)
            self._budget = delivery_budget(self._settings,
                                           self._state["load"])
            self._strategy = self._choose_strategy(rt)
            kb = self._settings.path("knowledge")
            gazetteer = load_gazetteer(BundleReader(kb / "bundle"))
            idx = connect(self._settings.app_support / "index.db")

            with profile.stage("normalize"):
                question = analyze(self._query, gaz=gazetteer)
            as_of = self._as_of or next(
                (m.data["iso"] for m in question.by_kind("date")
                 if m.confidence != "ambiguous"), None)
            question_entities = {m.canonical for m in question.matches
                                 if m.kind in ("entity", "standard",
                                               "identifier")}

            streams = EvidenceStreams(credit=self._stream_credit(rt))
            if not question_entities and _GLOBAL_MARKERS.search(self._query):
                communities = [r["page"] for r in idx.execute(
                    "SELECT DISTINCT page FROM chunks "
                    "WHERE page LIKE 'communities/%'")]
                streams.add("global",
                            self._first_chunks(idx, communities[:12]))
            with profile.stage("fts"):
                streams.add("fts", fts.search(self._settings, self._query,
                                              limit=8))
            if self._deep:
                with profile.stage("dense"):
                    streams.add("dense", dense.search(
                        self._settings, self._query, router=self._router))
            if question_entities:
                with profile.stage("entity_lookup"):
                    seed_weights = self._entity_page_weights(
                        idx, question_entities)
                    ranked = heapq.nlargest(20, seed_weights,
                                            key=seed_weights.__getitem__)
                    streams.add("entity", self._first_chunks(idx, ranked))
                # HippoRAG (v0.13): PPR semeado pelas páginas-entidade —
                # fatos a 1+ saltos de link da pergunta (associatividade)
                streams.add("graph",
                            self._graph_stream(idx, seed_weights, profile))
            trajectory: list[dict] = []
            if self._settings.flag("retrieval.descend"):
                with profile.stage("descend"):
                    pages, trajectory = descend.run(idx, self._query)
                    streams.add("descend", self._first_chunks(idx, pages))

            with profile.stage("fusion"):
                overlay = {r["page"]: r["status"] for r in idx.execute(
                    "SELECT page, status FROM page_overlay")}
                fused = streams.fuse(overlay=overlay, as_of=as_of,
                                     limit=self._budget["evidence_limit"])
            idx.close()
            profile.count("pages_considered", streams.pages_considered)
            profile.count("chunks_considered", streams.chunks_considered)

            threshold = float(self._settings.get("ask.abstain_threshold",
                                                 0.0))
            if fused.is_empty() or fused.top_score < threshold:
                out = self._cold_fallback(ask_id, fused, as_of, trajectory)
                out["profile"] = profile.close()
                return out

            with profile.stage("record_usage"):
                self._record_usage(rt, ask_id, fused)
            evidence = [{"page": h["page"], "resource": h.get("resource"),
                         "body": h["text"], "stale": bool(h.get("stale")),
                         "superseded": bool(h.get("superseded"))}
                        for h in fused.hits]
            with profile.stage("compose"):
                answer, via, blocked = self._compose(evidence)
            return {"answer": answer, "via": via, "blocked": blocked,
                    "abstained": False, "ask_id": ask_id,
                    "identity": parse_id(ask_id),
                    "uncertainty": fused.uncertainty,
                    "strategy": self._strategy,
                    "cognitive": {"load": self._state["load"],
                                  "declared": self._state["declared"]},
                    "evidence": evidence, "gaps": [],
                    "as_of": as_of, "trajectory": trajectory,
                    "profile": profile.close()}
        finally:
            rt.close()

    # -------------------------------------------------- camada cognitiva
    def _choose_strategy(self, rt) -> str:
        """Declarado vence observado (FR-14.3): perfil fixa a estratégia;
        em 'auto', roleta ∝ peso Hedge (exploração à EXP3 — estratégia
        boa aparece mais, nenhuma é silenciada)."""
        preferred = self._settings.get("profile.preferred_strategy", "auto")
        if preferred in STRATEGIES:
            return preferred
        stored = {r["strategy"]: r["weight"] for r in rt.execute(
            "SELECT strategy, weight FROM strategy_weights")}
        weights = [stored.get(s, 1.0) for s in STRATEGIES]
        pick = random.uniform(0, sum(weights))
        for strategy, weight in zip(STRATEGIES, weights):
            pick -= weight
            if pick <= 0:
                return strategy
        return STRATEGIES[0]

    # ------------------------------------------------------------ streams
    def _stream_credit(self, rt) -> dict[str, float]:
        return {r["stream"]: r["weight"] for r in
                rt.execute("SELECT stream, weight FROM stream_weights")}

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

    def _graph_stream(self, idx, seeds: dict[str, float],
                      profile: StageProfile) -> list[dict]:
        """PPR via ComputeKernel (ADR-39): o grafo vem do cache por
        geração (não é reconstruído a cada pergunta) e o backend
        (python/rust) é selecionável — Rust calcula o sinal; o
        SIGNIFICADO (quais páginas viram evidência) continua aqui."""
        if not seeds:
            return []
        from ..compute.graph_cache import cached_graph
        from ..compute.python_kernel import graph_generation
        with profile.stage("graph_load"):
            graph = cached_graph(
                self._kernel,
                index_path=str(self._settings.app_support / "index.db"),
                connection=idx, generation=graph_generation(idx))
        profile.count("graph_nodes", graph.nodes)
        profile.count("graph_edges", graph.edges)
        if not graph.nodes:
            return []
        with profile.stage("ppr"):
            ranked = self._kernel.personalized_pagerank(
                graph, seeds, top_k=12)
        return self._first_chunks(idx, [page for page, _ in ranked])

    @staticmethod
    def _first_chunks(idx, pages: list[str]) -> list[dict]:
        """§19 (ADR-39): UMA consulta com IN + MIN(ord) por página — o
        laço anterior fazia 1 SELECT por página (N+1). A ordem de
        `pages` (relevância) é preservada na saída."""
        if not pages:
            return []
        placeholders = ",".join("?" * len(pages))
        by_page = {r["page"]: dict(r) for r in idx.execute(
            f"SELECT id, page, text, resource, privacy, stale, valid_at, "
            f"invalid_at, superseded, MIN(ord) FROM chunks "
            f"WHERE page IN ({placeholders}) GROUP BY page", pages)}
        out = []
        for page in pages:
            row = by_page.get(page)
            if row:
                row.pop("MIN(ord)", None)
                out.append(row)
        return out

    # ---------------------------------------------------------- pós-fusão
    def _record_usage(self, rt, ask_id: str, fused) -> None:
        now = time.time()
        # contexto cognitivo da consulta (v0.18): estratégia usada, carga
        # vigente e confiança — a matéria-prima da calibração/metacognição
        rt.execute("INSERT OR REPLACE INTO ask_context"
                   "(ask_id, strategy, load, confidence) VALUES (?,?,?,?)",
                   (ask_id, self._strategy,
                    self._state["load"] if self._state["declared"] else None,
                    round(1.0 - fused.uncertainty, 4)))
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

    def _compose(self, evidence: list[dict]) -> tuple[str, str, bool]:
        numbered = "\n\n".join(
            f"[{i + 1}] ({e['page']}) {e['body'][:800]}"
            for i, e in enumerate(evidence))
        style = [_STRATEGY_HINT[self._strategy]]
        if self._budget["concise"]:            # CLT: carga alta ⇒ conciso
            style.append("A pessoa está com pouca capacidade disponível "
                         "agora: seja breve e evite abrir frentes novas.")
        if not self._settings.get("profile.analogies", True):
            style.append("Não use analogias.")
        prompt = (_PROMPT.format(query=self._query, evidence=numbered)
                  + "\nEstilo: " + " ".join(style))
        try:
            privacy = "local_only" if self._local_only else "api_allowed"
            r = self._router.complete(
                prompt, privacy=privacy, deep=self._deep,
                max_tokens=self._budget["max_tokens"])
            text, via = r["text"], r["via"]
            # QA-3: citação [n] sem evidência correspondente é proveniência
            # fabricada (vale para local: E api:) — degrada para o
            # extrativo, correto por construção; `via` sinaliza ao cliente
            if _invalid_citations(text, len(evidence)):
                return self._extractive(evidence), "local:extractive", False
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
