"""Revisão semanal em DOIS use cases (CQS: consulta ≠ comando).

ComputeWeeklyReview: levantamento puro, sem efeitos — o cockpit consome
direto. PublishWeeklyReview: subclasse do Template Method — materializa a
página passando pelo mesmo esqueleto imutável de toda página de máquina.
"""
from __future__ import annotations
import hashlib
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from .base import DraftPage, MachinePageUseCase, UseCase
from .reflect_usage import usage_candidates
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..settings import Settings


class ComputeWeeklyReview(UseCase):
    def __init__(self, settings: Settings):
        self._settings = settings

    def execute(self) -> dict:
        kb = self._settings.path("knowledge")
        reader = BundleReader(kb / "bundle")
        week = time.strftime("%Y-W%W")
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        new_pages, stale, decisions, questions = [], [], [], []
        tags: Counter = Counter()
        all_pages: list[str] = []
        for d in reader.iter_concepts():
            all_pages.append(d.rel_path)
            x = d.meta.model_dump(exclude_none=True)
            ts = d.meta.timestamp
            if ts and ts.replace(tzinfo=ts.tzinfo or timezone.utc) >= cutoff:
                new_pages.append(d.rel_path)
            if x.get("stale_as_of"):
                stale.append(d.rel_path)
            if d.meta.type == "decision":
                decisions.append(d.rel_path)
            if d.meta.type == "question":
                questions.append(d.rel_path)
            tags.update(d.meta.tags)
        idx = connect(self._settings.app_support / "index.db")
        linked = {r["dst"] for r in idx.execute(
            "SELECT DISTINCT dst FROM graph_edges")}
        idx.close()
        orphans = [p for p in all_pages if p not in linked]
        return {"week": week, "new_pages": new_pages, "orphans": orphans,
                "stale": stale, "decisions": decisions,
                "questions": questions, "top_tags": tags.most_common(12),
                **usage_candidates(self._settings)}


class PublishWeeklyReview(MachinePageUseCase):
    LOG_KIND = "Review"

    def __init__(self, settings: Settings, notify=None):
        super().__init__(settings, notify)
        self._data: dict = {}

    def _produce(self) -> DraftPage:
        data = ComputeWeeklyReview(self._settings).execute()
        self._data = data
        week = data["week"]

        def _list(items: list[str]) -> str:
            return "\n".join(f"- [{p}](/{p})" for p in items) or "- (nenhuma)"

        body = (
            f"# Revisão semanal {week}\n\n"
            f"## Novas páginas\n{_list(data['new_pages'])}\n\n"
            f"## Órfãos para linkar\n{_list(data['orphans'])}\n\n"
            f"## Stale para revisar\n{_list(data['stale'])}\n\n"
            f"## Decisões ativas\n{_list(data['decisions'])}\n\n"
            f"## Perguntas abertas\n{_list(data['questions'])}\n\n"
            f"## Tags mais usadas\n"
            + ("\n".join(f"- `{t}` × {n}" for t, n in data["top_tags"])
               or "- (nenhuma)") + "\n\n"
            f"## Ações sugeridas (reflect)\n"
            f"- Promover: "
            f"{', '.join(p['path'] for p in data['promote']) or '(nenhuma)'}\n"
            f"- Arquivar: "
            f"{', '.join(p['path'] for p in data['archive']) or '(nenhuma)'}\n"
            f"- Contestadas: {', '.join(data['contested']) or '(nenhuma)'}\n")
        return DraftPage(
            rel_path=f"reviews/{week}.md",
            title=f"Revisão semanal {week}", body=body,
            meta={"type": "review", "privacy": "local_only",
                  "generated_via": "local:review",
                  "source_sha256": hashlib.sha256(body.encode()).hexdigest()},
            log_message=f"revisão semanal {week}",
            commit_message=f"review: {week}")

    def _after_write(self, document, report) -> None:
        self._notify("review.done", {"page": document.rel_path})

    def _extra_result(self) -> dict:
        return self._data
