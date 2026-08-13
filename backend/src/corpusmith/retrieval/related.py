"""Páginas relacionadas (v0.13) — o gesto Zettelkasten do A-mem
(Xu et al., "A-mem: Agentic Memory for LLM Agents", arXiv:2502.12110)
em versão determinística: quando uma página é aberta, sugerimos vizinhas
por sobreposição de entidades ponderada por surprisal, EXCLUINDO as já
linkadas — o que sobra é exatamente o link que falta criar."""
from __future__ import annotations
from ..kernel.information import surprisal
from ..runtime.db import connect
from ..settings import Settings


def related_pages(settings: Settings, page: str, *, limit: int = 5) -> list[dict]:
    idx = connect(settings.app_support / "index.db")
    try:
        corpus = idx.execute("SELECT COUNT(DISTINCT page) c "
                             "FROM page_entities").fetchone()["c"]
        linked = {r["dst"] for r in idx.execute(
            "SELECT dst FROM graph_edges WHERE src=?", (page,))} \
            | {r["src"] for r in idx.execute(
                "SELECT src FROM graph_edges WHERE dst=?", (page,))} | {page}
        scores: dict[str, float] = {}
        shared: dict[str, list[str]] = {}
        for row in idx.execute(
                "SELECT other.page AS page, e.canonical AS canonical, "
                "other.n AS n, "
                "(SELECT COUNT(DISTINCT p2.page) FROM page_entities p2 "
                " WHERE p2.entity_id = mine.entity_id) AS df "
                "FROM page_entities mine "
                "JOIN page_entities other ON other.entity_id = mine.entity_id "
                "JOIN entities e ON e.id = mine.entity_id "
                "WHERE mine.page = ? AND other.page != ?", (page, page)):
            if row["page"] in linked:
                continue
            weight = row["n"] * surprisal(row["df"], max(corpus, 1))
            scores[row["page"]] = scores.get(row["page"], 0.0) + weight
            shared.setdefault(row["page"], []).append(row["canonical"])
        ranked = sorted(scores, key=lambda p: -scores[p])[:limit]
        return [{"page": p, "score": round(scores[p], 3),
                 "shared": sorted(set(shared[p]))[:6]} for p in ranked]
    finally:
        idx.close()
