"""ReflectOnUsage (v0.8 §8 como use case) + usage_candidates (consulta pura)."""
from __future__ import annotations
import json
import math
import time
from .base import UseCase
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


def usage_candidates(settings: Settings) -> dict:
    """Consulta pura (sem efeitos) — Dashboard e review consomem daqui."""
    rt = connect(settings.app_support / "runtime.db")
    idx = connect(settings.app_support / "index.db")
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


class ReflectOnUsage(UseCase):
    """Recalcula heat, agrega desfechos no overlay e devolve candidatos —
    NUNCA ação automática (arquivar ≠ apagar; Git é o backstop)."""

    def __init__(self, settings: Settings, notify=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        idx = connect(self._settings.app_support / "index.db")
        ratios = outcome_ratios(rt)
        self._recalculate_heat(rt, ratios)
        self._rebuild_overlay(idx, ratios)
        rt.close()
        idx.close()
        candidates = usage_candidates(self._settings)
        self._notify("reflect.done",
                     {"promote": len(candidates["promote"]),
                      "archive": len(candidates["archive"]),
                      "contested": len(candidates["contested"])})
        return candidates

    def _recalculate_heat(self, rt, ratios) -> None:
        for path, reads, cites, last in rt.execute(
                "SELECT path, reads, cites, last_seen FROM page_heat"
                ).fetchall():
            useful, dead = ratios.get(path, (0, 0))
            outcome = (useful / (useful + dead)) if (useful + dead) else 0.5
            score = (0.5 * _decay(last) * math.log1p(reads)
                     + 0.3 * math.log1p(cites) + 0.2 * outcome)
            rt.execute("UPDATE page_heat SET score=? WHERE path=?",
                       (score, path))
        rt.commit()

    def _rebuild_overlay(self, idx, ratios) -> None:
        idx.execute("DELETE FROM page_overlay")
        for page, (useful, dead) in ratios.items():
            total = useful + dead
            if total < 3:
                status = "tentative"
            elif useful / total >= 0.75:
                status = "preferred"
            elif dead / total >= 0.5:
                status = "contested"
            else:
                status = "tentative"
            idx.execute("INSERT OR REPLACE INTO page_overlay VALUES (?,?,?,?,?)",
                        (page, status, useful, dead, time.time()))
        idx.commit()
