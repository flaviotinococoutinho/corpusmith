"""Fusão RRF de FTS + denso (Parte V §7.3)."""
from __future__ import annotations

K = 60


def rrf(*result_lists: list[dict], limit: int = 8) -> list[dict]:
    scores: dict[int, float] = {}
    by_id: dict[int, dict] = {}
    for results in result_lists:
        for rank, r in enumerate(results):
            cid = r["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (K + rank + 1)
            by_id.setdefault(cid, r)
    ordered = sorted(scores, key=lambda c: -scores[c])[:limit]
    return [by_id[c] for c in ordered]
