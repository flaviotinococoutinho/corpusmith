"""CurationFacade — a memória sob governo humano: promover, depreciar,
auditar, revisar, refletir."""
from __future__ import annotations
from ..harness.findings import Findings
from ..settings import Settings
from ..usecases.lint_bundle import LintBundle
from ..usecases.mark_stale import MarkPageStale
from ..usecases.promote_memory import PromoteToMemory
from ..usecases.reflect_usage import ReflectOnUsage, usage_candidates
from ..usecases.weekly_review import ComputeWeeklyReview, PublishWeeklyReview


class CurationFacade:
    def __init__(self, settings: Settings):
        self._settings = settings

    def promote(self, *, kind: str, title: str, content: str,
                source: str = "chat", privacy: str = "local_only",
                description: str | None = None,
                tags: list[str] | None = None) -> dict:
        return PromoteToMemory(self._settings, kind=kind, title=title,
                               content=content, source=source,
                               privacy=privacy, description=description,
                               tags=tags).execute()

    def mark_stale(self, page_path: str) -> dict:
        return MarkPageStale(self._settings, page_path).execute()

    def lint(self, mode: str = "write") -> Findings:
        return LintBundle(self._settings, mode).execute()

    def weekly_review(self) -> dict:
        """Levantamento puro — sem efeitos (CQS)."""
        return ComputeWeeklyReview(self._settings).execute()

    def publish_review(self, notify=None) -> dict:
        return PublishWeeklyReview(self._settings, notify).execute()

    def reflect(self, notify=None) -> dict:
        return ReflectOnUsage(self._settings, notify).execute()

    def reflect_candidates(self) -> dict:
        return usage_candidates(self._settings)
