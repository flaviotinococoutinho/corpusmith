"""Descida hierárquica L0→L1 (v0.8 §9) — Directory Recursive Retrieval do
OpenViking reduzido ao essencial: FTS sobre page_levels, determinístico e
barato; a trajetória vai para o Cockpit (transparência do caminho)."""
from __future__ import annotations
from collections import defaultdict
from .fts import fts_terms as _fts_terms


def run(idx, query: str, *, top_dirs: int = 3, per_dir: int = 4):
    """L0 (descrições) → escolhe diretórios → L1 (headings) → páginas.
    Devolve (páginas, trajetória)."""
    terms = _fts_terms(query)
    l0 = idx.execute(
        "SELECT pl.page, bm25(fts_levels) r FROM fts_levels "
        "JOIN page_levels pl ON pl.rowid = fts_levels.rowid "
        "WHERE fts_levels MATCH ? AND pl.level = 0 ORDER BY r LIMIT 40",
        (terms,)).fetchall()
    by_dir: dict[str, list] = defaultdict(list)
    for page, r in l0:
        by_dir[page.split("/")[0]].append((r, page))
    dirs = sorted(by_dir, key=lambda d: min(r for r, _ in by_dir[d]))[:top_dirs]
    pages, trajectory = [], []
    for d in dirs:
        l1 = idx.execute(
            "SELECT pl.page, bm25(fts_levels) r FROM fts_levels "
            "JOIN page_levels pl ON pl.rowid = fts_levels.rowid "
            "WHERE fts_levels MATCH ? AND pl.level = 1 AND pl.page LIKE ? "
            "ORDER BY r LIMIT ?", (terms, d + "/%", per_dir)).fetchall()
        picked = [p for p, _ in l1] or [p for _, p in sorted(by_dir[d])[:per_dir]]
        pages.extend(picked)
        trajectory.append({"dir": d, "picked": picked})
    return pages, trajectory
