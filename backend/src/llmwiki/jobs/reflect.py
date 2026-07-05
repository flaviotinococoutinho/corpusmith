"""Adapter do job `reflect` (v0.9): lógica em usecases/reflect_usage.py."""
from __future__ import annotations
from ..facades.curation import CurationFacade
from ..settings import Settings


def candidates(s: Settings) -> dict:
    return CurationFacade(s).reflect_candidates()


def run(s: Settings, payload: dict, emit) -> dict:
    def notify(type: str, data: dict | None = None):
        emit(type, data or {})

    return CurationFacade(s).reflect(notify=notify)
