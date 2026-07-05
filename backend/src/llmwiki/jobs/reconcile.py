"""Reconciliador ADD/UPDATE/SUPERSEDE/NOOP (v0.8 §5) — pipeline mem0
adaptado ao gate de escrita: sinais determinísticos primeiro (identificador
forte compartilhado ⇒ mesmo objeto do mundo), similaridade depois, LLM
LOCAL só na zona cinzenta. Toda decisão vai para reconcile_log (auditoria).
"""
from __future__ import annotations
import json
from ..okf.document import OKFDocument
from ..runtime.db import connect
from ..settings import Settings

HI, LO = 0.82, 0.55          # cortes de similaridade (calibráveis via bench)


def _strong_ids(report) -> set[str]:
    return {m.canonical for m in report.matches
            if m.kind == "identifier"
            and m.subkind in ("doi", "isbn", "issn", "arxiv", "git_sha")
            and m.valid is not False}


def _entity_jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def plan(s: Settings, candidate: OKFDocument, report, router=None) -> dict:
    """Decide ADD | UPDATE | SUPERSEDE | NOOP para uma página gerada por
    máquina. Nunca escreve nada — devolve o plano; compile.py aplica."""
    idx = connect(s.app_support / "index.db")
    try:
        ids = _strong_ids(report)
        cand_ents = set(report.entities_frontmatter(limit=64))

        # 1) determinístico: identificador forte compartilhado
        if ids:
            q = ("SELECT DISTINCT pe.page FROM page_entities pe "
                 "JOIN entities e ON e.id = pe.entity_id "
                 f"WHERE e.canonical IN ({','.join('?' * len(ids))})")
            for (page,) in idx.execute(q, tuple(ids)).fetchall():
                if page != candidate.rel_path:
                    return {"op": "UPDATE", "target": page, "score": 1.0,
                            "reason": "identificador forte compartilhado: "
                                      f"{sorted(ids)[:3]}",
                            "confidence": "extracted"}

        # 2) similaridade: FTS no título + Jaccard de entidades
        title = candidate.meta.title or candidate.rel_path
        terms = " OR ".join(f'"{w}"' for w in title.split()[:6] if len(w) > 2) \
            or f'"{title}"'
        try:
            fts = idx.execute(
                "SELECT c.page, MIN(bm25(chunks_fts)) r FROM chunks_fts "
                "JOIN chunks c ON c.id = chunks_fts.rowid "
                "WHERE chunks_fts MATCH ? GROUP BY c.page "
                "ORDER BY r LIMIT 8", (terms,)).fetchall()
        except Exception:
            fts = []
        scored: list[tuple[float, str]] = []
        for i, (page, _rank) in enumerate(fts):
            if page == candidate.rel_path:
                continue
            ents = {r[0] for r in idx.execute(
                "SELECT e.canonical FROM page_entities pe "
                "JOIN entities e ON e.id = pe.entity_id WHERE pe.page = ?",
                (page,)).fetchall()}
            score = 0.5 * (1.0 / (1.0 + i)) \
                  + 0.5 * _entity_jaccard(cand_ents, ents)
            scored.append((score, page))
        scored.sort(reverse=True)

        if not scored or scored[0][0] < LO:
            return {"op": "ADD", "target": None,
                    "score": scored[0][0] if scored else 0,
                    "reason": "nenhum candidato acima do corte",
                    "confidence": "extracted"}
        best_score, best_page = scored[0]
        if best_score >= HI:
            return {"op": "UPDATE", "target": best_page, "score": best_score,
                    "reason": "similaridade alta (título+entidades)",
                    "confidence": "inferred"}

        # 3) zona cinzenta: LLM LOCAL decide (nunca API — barato e privado)
        if router is not None and s.flag("reconcile.llm_arbiter"):
            prompt = (f"Página candidata: '{candidate.meta.title}' — "
                      f"{(candidate.meta.description or '')[:200]}\n"
                      f"Página existente: '{best_page}'.\n"
                      'Responda SOMENTE JSON: {"op":"ADD|UPDATE|SUPERSEDE|NOOP"}. '
                      "UPDATE se é o mesmo conceito; SUPERSEDE se a nova substitui "
                      "a antiga; NOOP se nada novo; ADD se são conceitos distintos.")
            try:
                r = router.complete(prompt, privacy="local_only", max_tokens=32)
                op = json.loads(r["text"]).get("op", "ADD")
                if op in ("ADD", "UPDATE", "SUPERSEDE", "NOOP"):
                    return {"op": op,
                            "target": best_page if op != "ADD" else None,
                            "score": best_score, "reason": "árbitro LLM local",
                            "confidence": "ambiguous"}
            except Exception:
                pass
        return {"op": "ADD", "target": None, "score": best_score,
                "reason": "zona cinzenta sem árbitro — precisão > recall",
                "confidence": "ambiguous"}
    finally:
        idx.close()


def log(s: Settings, candidate: str, decision: dict) -> None:
    rt = connect(s.app_support / "runtime.db")
    rt.execute("INSERT INTO reconcile_log(candidate, op, target, reason, signals) "
               "VALUES (?,?,?,?,?)",
               (candidate, decision["op"], decision.get("target"),
                decision["reason"], json.dumps({"score": decision.get("score"),
                                                "confidence": decision["confidence"]})))
    rt.commit()
    rt.close()
