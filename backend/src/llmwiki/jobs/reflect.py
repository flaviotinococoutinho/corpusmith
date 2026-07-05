"""Job `reflect` (v0.8 §8): heat score + desfechos → overlay de qualidade.

1) heat = 0.5·recência·log(1+leituras) + 0.3·log(1+citações) + 0.2·desfecho
2) 3+ desfechos decidem preferred/tentative/contested (graphify reflect)
3) candidatos a promoção/arquivamento vão para o humano — NUNCA ação
   automática (arquivar ≠ apagar; Git é o backstop).
"""
from __future__ import annotations
import json
import math
import time
from ..runtime.db import connect
from ..settings import Settings

HALF_LIFE_DAYS = 30.0


def _decay(last_seen: float | None) -> float:
    if not last_seen:
        return 0.0
    dt_days = max(0.0, (time.time() - last_seen) / 86_400)
    return math.exp(-math.log(2) * dt_days / HALF_LIFE_DAYS)


def outcome_ratios(rt) -> dict[str, tuple[int, int]]:
    ratios: dict[str, tuple[int, int]] = {}
    for pages, verdict in rt.execute("SELECT pages, verdict FROM ask_outcomes"):
        for p in json.loads(pages or "[]"):
            u, d = ratios.get(p, (0, 0))
            ratios[p] = (u + (verdict == "useful"),
                         d + (verdict in ("dead_end", "corrected")))
    return ratios


def candidates(s: Settings) -> dict:
    """Consulta pura (sem efeitos) — Dashboard e review consomem daqui."""
    rt = connect(s.app_support / "runtime.db")
    idx = connect(s.app_support / "index.db")
    promote = [dict(r) for r in rt.execute(
        "SELECT path, score FROM page_heat WHERE path LIKE 'inbox/%' "
        "AND score > 0.6 ORDER BY score DESC LIMIT 10")]
    archive = [dict(r) for r in rt.execute(
        "SELECT path, score FROM page_heat WHERE score < 0.05 "
        "AND last_seen < unixepoch() - 90*86400 ORDER BY score LIMIT 10")]
    contested = [r["page"] for r in idx.execute(
        "SELECT page FROM page_overlay WHERE status='contested'")]
    rt.close()
    idx.close()
    return {"promote": promote, "archive": archive, "contested": contested}


def run(s: Settings, payload: dict, emit) -> dict:
    rt = connect(s.app_support / "runtime.db")
    idx = connect(s.app_support / "index.db")

    # (1) heat
    ratios = outcome_ratios(rt)
    for path, reads, cites, last in rt.execute(
            "SELECT path, reads, cites, last_seen FROM page_heat").fetchall():
        u, d = ratios.get(path, (0, 0))
        outcome = (u / (u + d)) if (u + d) else 0.5
        score = (0.5 * _decay(last) * math.log1p(reads)
                 + 0.3 * math.log1p(cites) + 0.2 * outcome)
        rt.execute("UPDATE page_heat SET score=? WHERE path=?", (score, path))
    rt.commit()

    # (2) overlay: 3+ desfechos decidem o status
    idx.execute("DELETE FROM page_overlay")
    for p, (u, d) in ratios.items():
        if u + d < 3:
            status = "tentative"
        elif u / (u + d) >= 0.75:
            status = "preferred"
        elif d / (u + d) >= 0.5:
            status = "contested"
        else:
            status = "tentative"
        idx.execute("INSERT OR REPLACE INTO page_overlay VALUES (?,?,?,?,?)",
                    (p, status, u, d, time.time()))
    idx.commit()
    rt.close()
    idx.close()

    # (3) candidatos para o humano
    cand = candidates(s)
    emit("reflect.done",
         {"promote": len(cand["promote"]), "archive": len(cand["archive"]),
          "contested": len(cand["contested"])})
    return cand
