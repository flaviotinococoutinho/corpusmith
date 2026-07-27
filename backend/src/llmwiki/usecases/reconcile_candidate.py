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


class ReconcileCandidate(UseCase):
    """Escada de reconciliação: identificador forte, similaridade, árbitro.

    **Estado medido do degrau de similaridade**: morto em produção desde a
    v0.9 — ver o comentário em `_by_similarity`. `similarity_error` guarda o
    motivo quando a consulta falha, para o defeito parar de ser indistinguível
    de "não havia candidato".
    """

    similarity_error: str | None = None

    def __init__(self, settings: Settings, candidate: OKFDocument,
                 report, router=None):
        self._settings = settings
        self._candidate = candidate
        self._report = report
        self._router = router

    def execute(self) -> dict:
        idx = connect(self._settings.app_support / "index.db")
        try:
            deterministic = self._by_strong_identifier(idx)
            if deterministic:
                return deterministic
            scored = self._by_similarity(idx)
            if not scored or scored[0][0] < LO:
                return self._decision("ADD", None,
                                      scored[0][0] if scored else 0.0,
                                      "nenhum candidato acima do corte",
                                      "extracted")
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
        # DEFEITO CONHECIDO, e o `except` agora é AUDÍVEL em vez de mudo.
        #
        # Verificado por execução em SQLite 3.45.1: `MIN(bm25(chunks_fts))`
        # levanta `OperationalError: unable to use function bm25 in the
        # requested context` — SEMPRE, não em caso de borda. O agregado não
        # pode envolver a função de ranking do FTS5. Com o `except Exception`
        # cego que estava aqui, `matches` saía vazio em TODA execução desde a
        # v0.9, e com isso o degrau de similaridade, os limiares HI/LO, o NCD
        # e o árbitro LLM viraram código morto em produção — sem que nada
        # acusasse, porque a degradação era indistinguível de "não achei
        # candidato".
        #
        # A correção da SQL é UMA LINHA (`MIN(bm25(...))` -> `bm25(...)`,
        # sem o GROUP BY) e NÃO é feita aqui de propósito: ela ATIVA o árbitro
        # LLM no caminho de escrita, e o `AGENTS.md` §8 exige RFC para isso.
        # Fazer o gesto de uma linha seria introduzir decisão de modelo
        # generativo sobre o canônico por efeito colateral de um conserto.
        #
        # O que muda AQUI é só o silêncio: a falha passa a ser registrada e
        # contável. O comportamento (degradar para lista vazia) é idêntico.
        matches = []
        try:
            matches = idx.execute(
                "SELECT c.page, MIN(bm25(chunks_fts)) r FROM chunks_fts "
                "JOIN chunks c ON c.id = chunks_fts.rowid "
                "WHERE chunks_fts MATCH ? GROUP BY c.page "
                "ORDER BY r LIMIT 8", (terms,)).fetchall()
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

    @staticmethod
    def _decision(op, target, score, reason, confidence) -> dict:
        return {"op": op, "target": target, "score": score,
                "reason": reason, "confidence": confidence}


def log_decision(settings: Settings, candidate: str, decision: dict) -> None:
    """Trilha de auditoria (padrão ai-memory) — toda decisão é registrada."""
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("INSERT INTO reconcile_log(candidate, op, target, reason, signals) "
               "VALUES (?,?,?,?,?)",
               (candidate, decision["op"], decision.get("target"),
                decision["reason"],
                json.dumps({"score": decision.get("score"),
                            "confidence": decision["confidence"]})))
    rt.commit()
    rt.close()
