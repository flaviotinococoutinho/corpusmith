"""ReconcileCandidate (v0.8 §5, reformulado como use case na v0.9).

Escada de decisão ADD/UPDATE/SUPERSEDE/NOOP, do mais determinístico ao
menos: identificador forte compartilhado → similaridade composta → LLM
local (flag). A similaridade composta agora inclui a Normalized
Compression Distance (Cilibrasi & Vitányi 2005): dois textos sobre o mesmo
objeto do mundo comprimem-se mutuamente — sinal barato, sem modelo, imune
a paráfrase superficial.

    score = 0.4·rank(FTS título) + 0.3·Jaccard(entidades) + 0.3·(1 − NCD)
"""
from __future__ import annotations
import sqlite3
import json
from .base import UseCase
from ..kernel.information import ncd
from ..okf.bundle import BundleReader
from ..okf.document import OKFDocument
from ..runtime.db import connect
from ..settings import Settings

HI, LO = 0.82, 0.55          # cortes de similaridade (calibráveis via bench)
STRONG_IDS = ("doi", "isbn", "issn", "arxiv", "git_sha")
_PAGE_LIMIT = 8              # páginas candidatas consideradas
_CHUNK_LIMIT = 64            # chunks lidos p/ render `_PAGE_LIMIT` páginas


class ReconcileCandidate(UseCase):
    """Escada de reconciliação: identificador forte, similaridade, árbitro.

    O degrau de similaridade esteve **morto da v0.9 ao F3-PR0** (RFC-002) e
    dois atributos existem para que uma falha volte a ser distinguível de uma
    ausência: `similarity_error` (a consulta estourou) e `index_stale` (a
    decisão saiu de uma projeção atrasada). Sem eles, "não achei candidato"
    responde tanto por "procurei e não há" quanto por "não consegui procurar",
    que foi exatamente como o defeito sobreviveu a três versões.
    """

    similarity_error: str | None = None
    index_stale: str | None = None

    def __init__(self, settings: Settings, candidate: OKFDocument,
                 report, router=None):
        self._settings = settings
        self._candidate = candidate
        self._report = report
        self._router = router

    def execute(self) -> dict:
        # AUSÊNCIA DE EVIDÊNCIA num índice atrasado não é evidência de ausência
        # — é assim que nascem duas páginas canônicas vivas com o MESMO DOI
        # (achado B2 da auditoria, reproduzido). Negar a escrita não é opção: o
        # documento precisa entrar. O que não pode é entrar como se a busca
        # tivesse sido conclusiva.
        atraso = self.index_stale = self._ensure_fresh_projection()
        idx = connect(self._settings.app_support / "index.db")
        try:
            deterministic = self._by_strong_identifier(idx)
            if deterministic:
                return deterministic
            scored = self._by_similarity(idx)
            if not scored or scored[0][0] < LO:
                return self._decision(
                    "ADD", None, scored[0][0] if scored else 0.0,
                    ("nenhum candidato acima do corte, mas o índice está "
                     f"atrasado ({atraso}) — duplicata possível"
                     if atraso else "nenhum candidato acima do corte"),
                    "ambiguous" if atraso else "extracted")
            best_score, best_page = scored[0]
            if best_score >= HI:
                return self._decision("UPDATE", best_page, best_score,
                                      "similaridade alta (título+entidades+NCD)",
                                      "inferred")
            arbitrated = self._by_local_arbiter(best_page, best_score)
            if arbitrated:
                return arbitrated
            return self._decision("ADD", None, best_score,
                                  "zona cinzenta sem árbitro — precisão > recall",
                                  "ambiguous")
        finally:
            idx.close()

    # ------------------------------------------------------------- etapas
    def _ensure_fresh_projection(self) -> str | None:
        """Deixa o índice fresco antes de decidir; devolve o atraso restante.

        `index.db` é PROJEÇÃO, e esta escada o usa como AUTORIDADE: a decisão
        ADD/UPDATE/SUPERSEDE sobre a página canônica sai do que ele contém. Um
        índice atrasado esconde a página que já existe e a escada responde
        ADD — reproduzido na auditoria (B2) com duas páginas canônicas vivas
        para o mesmo DOI.

        A reindexação é INCREMENTAL e delta de git: quando o índice já está
        fresco isto custa uma leitura de checkpoint; quando não está, custa
        exatamente as páginas que mudaram, que é o preço de decidir sobre um
        estado real. Roda **uma vez**: se ainda assim não ficar fresco, o
        motivo volta e a decisão o carrega, em vez de o laço tentar de novo."""
        from ..runtime.checkpoints import verify
        atrasado = self._atraso(verify(self._settings))
        if atrasado is None:
            return None
        try:
            from ..retrieval.fts import rebuild_index
            rebuild_index(self._settings)
        except Exception as e:                           # noqa: BLE001
            return f"{atrasado} (reindexação falhou: {type(e).__name__})"
        return self._atraso(verify(self._settings))

    @staticmethod
    def _atraso(vereditos) -> str | None:
        """Estado do checkpoint `index`, ou None se fresco.

        `absent` conta como atraso aqui — e não conta como defeito no doctor
        (ADR-46). São perguntas diferentes: para o doctor, instalação nova não
        tem derivação velha, tem derivação nenhuma; para esta escada, índice
        que nunca foi computado esconde tanto quanto índice velho."""
        for v in vereditos:
            if v.derivation == "index":
                return None if v.state == "fresh" else v.state
        return "unknown"

    def _by_strong_identifier(self, idx) -> dict | None:
        ids = {m.canonical for m in self._report.matches
               if m.kind == "identifier" and m.subkind in STRONG_IDS
               and m.valid is not False}
        if not ids:
            return None
        query = ("SELECT DISTINCT pe.page FROM page_entities pe "
                 "JOIN entities e ON e.id = pe.entity_id "
                 f"WHERE e.canonical IN ({','.join('?' * len(ids))})")
        for (page,) in idx.execute(query, tuple(ids)).fetchall():
            if page != self._candidate.rel_path:
                return self._decision(
                    "UPDATE", page, 1.0,
                    f"identificador forte compartilhado: {sorted(ids)[:3]}",
                    "extracted")
        # base fria (v0.12): memória congelada com o mesmo objeto do mundo
        # é RECICLADA em vez de duplicada — o esquecimento se desfaz sozinho
        from .cold_memory import cold_by_strong_id
        frozen = cold_by_strong_id(self._settings, ids)
        if frozen and frozen != self._candidate.rel_path:
            return self._decision(
                "RECYCLE", frozen, 1.0,
                f"memória fria com o mesmo identificador: {sorted(ids)[:3]}",
                "extracted")
        return None

    def _by_similarity(self, idx) -> list[tuple[float, str]]:
        title = self._candidate.meta.title or self._candidate.rel_path
        terms = " OR ".join(f'"{w}"' for w in title.split()[:6]
                            if len(w) > 2) or f'"{title}"'
        # O degrau esteve MORTO da v0.9 até o F3-PR0 (RFC-002). `MIN(bm25(...))`
        # levanta `OperationalError: unable to use function bm25 in the
        # requested context` — SEMPRE, em toda execução: uma função auxiliar do
        # FTS5 não pode aparecer dentro de agregado. Um `except Exception` cego
        # engolia, `matches` saía vazio, e o degrau de similaridade, os cortes
        # HI/LO, o NCD e o árbitro LLM eram código morto em produção sem que
        # nada acusasse — a degradação era indistinguível de "não achei nada".
        #
        # A correção NÃO é o `MIN` virar `bm25` no mesmo SELECT: a subquery
        # também estoura (medido; a restrição é da consulta que carrega o
        # MATCH, não do nível de aninhamento). O ranking sai POR CHUNK e a
        # redução por página é feita aqui, mantendo o melhor rank de cada uma
        # — o que também corrige um segundo erro que o agregado escondia: sem
        # deduplicar, uma página com muitos chunks ocuparia várias posições e
        # inflaria o termo `1/(1+position)` do score.
        #
        # `LIMIT` é sobre CHUNKS, então precisa folga para render 8 páginas
        # distintas; o corte final volta a ser de páginas.
        matches: list[tuple[str, float]] = []
        try:
            melhor: dict[str, float] = {}
            for page, rank in idx.execute(
                    "SELECT c.page, bm25(chunks_fts) r FROM chunks_fts "
                    "JOIN chunks c ON c.id = chunks_fts.rowid "
                    "WHERE chunks_fts MATCH ? ORDER BY r LIMIT ?",
                    (terms, _CHUNK_LIMIT)).fetchall():
                if page not in melhor:      # já vem ordenado por rank
                    melhor[page] = rank
            matches = sorted(melhor.items(), key=lambda kv: kv[1])[:_PAGE_LIMIT]
        except sqlite3.OperationalError as e:
            self.similarity_error = f"{type(e).__name__}: {e}"
        except Exception as e:                           # noqa: BLE001
            self.similarity_error = f"{type(e).__name__}: {e}"
        candidate_entities = set(self._report.entities_frontmatter(limit=64))
        reader = BundleReader(self._settings.path("knowledge") / "bundle")
        scored: list[tuple[float, str]] = []
        for position, (page, _rank) in enumerate(matches):
            if page == self._candidate.rel_path:
                continue
            entities = {r[0] for r in idx.execute(
                "SELECT e.canonical FROM page_entities pe "
                "JOIN entities e ON e.id = pe.entity_id WHERE pe.page = ?",
                (page,)).fetchall()}
            jaccard = (len(candidate_entities & entities)
                       / len(candidate_entities | entities)
                       if candidate_entities | entities else 0.0)
            compression = self._compression_affinity(reader, page)
            score = (0.4 * (1.0 / (1.0 + position))
                     + 0.3 * jaccard + 0.3 * compression)
            scored.append((score, page))
        scored.sort(reverse=True)
        return scored

    def _compression_affinity(self, reader: BundleReader, page: str) -> float:
        """1 − NCD entre os corpos: alto quando os textos se explicam."""
        try:
            existing = reader.load(page)
        except Exception:
            return 0.0
        return 1.0 - ncd(self._candidate.body[:8_000], existing.body[:8_000])

    def _by_local_arbiter(self, best_page: str, best_score: float) -> dict | None:
        if self._router is None or \
           not self._settings.flag("reconcile.llm_arbiter"):
            return None
        prompt = (f"Página candidata: '{self._candidate.meta.title}' — "
                  f"{(self._candidate.meta.description or '')[:200]}\n"
                  f"Página existente: '{best_page}'.\n"
                  'Responda SOMENTE JSON: {"op":"ADD|UPDATE|SUPERSEDE|NOOP"}. '
                  "UPDATE se é o mesmo conceito; SUPERSEDE se a nova substitui "
                  "a antiga; NOOP se nada novo; ADD se são conceitos distintos.")
        try:
            r = self._router.complete(prompt, privacy="local_only",
                                      max_tokens=32)
            op = json.loads(r["text"]).get("op", "ADD")
            if op in ("ADD", "UPDATE", "SUPERSEDE", "NOOP"):
                return self._decision(op,
                                      best_page if op != "ADD" else None,
                                      best_score, "árbitro LLM local",
                                      "ambiguous")
        except Exception:
            pass
        return None

    def _decision(self, op, target, score, reason, confidence) -> dict:
        """Toda decisão carrega o que ATRAPALHOU a tomá-la.

        As chaves de diagnóstico só aparecem quando há o que declarar — e
        `log_decision` as persiste, para que "quantas decisões saíram de um
        índice atrasado?" seja uma consulta e não uma suposição."""
        decisao = {"op": op, "target": target, "score": score,
                   "reason": reason, "confidence": confidence}
        if self.index_stale:
            decisao["index_stale"] = self.index_stale
        if self.similarity_error:
            decisao["similarity_error"] = self.similarity_error
        return decisao


def log_decision(settings: Settings, candidate: str, decision: dict) -> None:
    """Trilha de auditoria (padrão ai-memory) — toda decisão é registrada."""
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("INSERT INTO reconcile_log(candidate, op, target, reason, signals) "
               "VALUES (?,?,?,?,?)",
               (candidate, decision["op"], decision.get("target"),
                decision["reason"],
                json.dumps({"score": decision.get("score"),
                            "confidence": decision["confidence"],
                            **{k: decision[k] for k in
                               ("index_stale", "similarity_error")
                               if decision.get(k)}})))
    rt.commit()
    rt.close()
