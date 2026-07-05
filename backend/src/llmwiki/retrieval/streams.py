"""EvidenceStreams — coleção de primeira classe dos streams de retrieval
(v0.9). Encapsula tudo que o /ask fazia inline:

- fusão RRF ponderada por CRÉDITO de stream (Hedge sobre os desfechos —
  kernel.information.hedge): cada stream é um "expert"; quem acerta ganha
  peso, quem leva a becos perde — com clamp para preservar exploração;
- boost do overlay (preferred +15% · contested −20%);
- partição temporal (válidas em `as_of` primeiro);
- INCERTEZA: entropia normalizada da distribuição fundida — massa de score
  espalhada significa "não sei onde está a resposta";
- proveniência página→streams (persistida para fechar o laço do Hedge).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from ..kernel.information import shannon_entropy

RRF_K = 60


def _valid_at(hit: dict, as_of: str) -> bool:
    va, ia = hit.get("valid_at"), hit.get("invalid_at")
    return (not va or str(va)[:len(as_of)] <= as_of) and \
           (not ia or str(ia)[:len(as_of)] > as_of)


@dataclass
class FusedEvidence:
    hits: list[dict] = field(default_factory=list)
    top_score: float = 0.0
    uncertainty: float = 0.0                      # entropia normalizada [0,1]
    provenance: dict[str, set[str]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.hits

    def pages(self) -> list[str]:
        return [h["page"] for h in self.hits]


class EvidenceStreams:
    def __init__(self, credit: dict[str, float] | None = None):
        self._streams: list[tuple[str, list[dict]]] = []
        self._credit = credit or {}

    def add(self, name: str, hits: list[dict]) -> None:
        if hits:
            self._streams.append((name, hits))

    def fuse(self, *, overlay: dict[str, str] | None = None,
             as_of: str | None = None, limit: int = 8) -> FusedEvidence:
        scores: dict[int, float] = {}
        by_id: dict[int, dict] = {}
        provenance: dict[str, set[str]] = {}
        for name, results in self._streams:
            weight = self._credit.get(name, 1.0)
            for rank, hit in enumerate(results):
                cid = hit["id"]
                scores[cid] = scores.get(cid, 0.0) + weight / (RRF_K + rank + 1)
                by_id.setdefault(cid, hit)
                provenance.setdefault(hit["page"], set()).add(name)
        for cid, hit in by_id.items():
            factor = {"preferred": 1.15, "contested": 0.8}.get(
                (overlay or {}).get(hit["page"]), 1.0)
            scores[cid] *= factor
        ordered = sorted(by_id.values(), key=lambda h: -scores[h["id"]])
        if as_of:
            ordered = [h for h in ordered if _valid_at(h, as_of)] \
                    + [h for h in ordered if not _valid_at(h, as_of)]
        hits = ordered[:limit]
        return FusedEvidence(
            hits=hits,
            top_score=scores.get(hits[0]["id"], 0.0) if hits else 0.0,
            uncertainty=shannon_entropy(
                [scores[h["id"]] for h in ordered[:12]]),
            provenance={h["page"]: provenance.get(h["page"], set())
                        for h in hits})
