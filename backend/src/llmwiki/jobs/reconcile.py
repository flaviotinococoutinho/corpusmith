"""Adapter de compatibilidade (v0.9): a lógica de reconciliação vive em
usecases/reconcile_candidate.py; `plan`/`log` mantêm o contrato v0.8."""
from __future__ import annotations
from ..okf.document import OKFDocument
from ..settings import Settings
from ..usecases.reconcile_candidate import (ReconcileCandidate, log_decision,
                                            HI, LO)

__all__ = ["plan", "log", "HI", "LO"]


def plan(s: Settings, candidate: OKFDocument, report, router=None) -> dict:
    return ReconcileCandidate(s, candidate, report, router).execute()


def log(s: Settings, candidate: str, decision: dict) -> None:
    log_decision(s, candidate, decision)
