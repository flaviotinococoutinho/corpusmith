"""Adapter do job `review_weekly` (v0.9): compute() e run() delegam para
os use cases (CQS: ComputeWeeklyReview é consulta; PublishWeeklyReview é
comando via Template Method)."""
from __future__ import annotations
from ..facades.curation import CurationFacade
from ..settings import Settings


def compute(s: Settings) -> dict:
    return CurationFacade(s).weekly_review()


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    result = CurationFacade(s).publish_review(notify=notify)
    if result.get("commit"):
        # quem escreve no bundle reindexa (mesma regra do job `leiden`):
        # sem isto o commit da review deixava INV-002 vermelho até o
        # próximo rebuild — visto na 1ª CI de segunda-feira (package smoke)
        from ..retrieval.fts import rebuild_index
        rebuild_index(s)
    return result
