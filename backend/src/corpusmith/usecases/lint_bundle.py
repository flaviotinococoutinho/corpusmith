"""LintBundle — fonte ÚNICA da auditoria (CLI `okf lint` == painel
Qualidade, invariante desde a v0.7)."""
from __future__ import annotations
from .base import UseCase
from ..harness.findings import Findings
from ..harness.runner import HarnessRunner
from ..okf.bundle import BundleReader
from ..okf.git_store import GitStore
from ..settings import Settings


class LintBundle(UseCase):
    def __init__(self, settings: Settings, mode: str = "write"):
        self._settings = settings
        self._mode = mode

    def execute(self) -> Findings:
        kb = self._settings.path("knowledge")
        bundle = kb / "bundle"
        runner = HarnessRunner(BundleReader(bundle), GitStore(kb))
        return runner.lint_bundle(bundle, mode=self._mode)
