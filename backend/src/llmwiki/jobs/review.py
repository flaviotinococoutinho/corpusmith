"""Revisão semanal (Parte V §7 + Manual Ap. C, com o split da v0.7 §5.3):
`compute()` faz TODO o levantamento sem escrever nada — o cockpit consome
direto (`GET /cockpit/review`); `run()` materializa a página e commita.
"""
from __future__ import annotations
import hashlib
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from ..okf.bundle import BundleReader
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..runtime.db import connect
from ..settings import Settings


def compute(s: Settings) -> dict:
    """Levantamento da semana (novas páginas, órfãos, stale, decisões,
    perguntas, tags) — SEM efeitos colaterais."""
    kb = s.path("knowledge")
    reader = BundleReader(kb / "bundle")
    week = time.strftime("%Y-W%W")
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    new_pages: list[str] = []
    stale: list[str] = []
    decisions: list[str] = []
    questions: list[str] = []
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

    idx = connect(s.app_support / "index.db")
    linked = {r["dst"] for r in idx.execute(
        "SELECT DISTINCT dst FROM graph_edges")}
    idx.close()
    orphans = [p for p in all_pages if p not in linked]

    return {"week": week, "new_pages": new_pages, "orphans": orphans,
            "stale": stale, "decisions": decisions, "questions": questions,
            "top_tags": tags.most_common(12)}


def run(s: Settings, payload: dict, emit) -> dict:
    data = compute(s)
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
           or "- (nenhuma)") + "\n")

    doc = OKFDocument(
        rel_path=f"reviews/{week}.md",
        body=body,
        meta=OKFFrontMatter(
            type="review", title=f"Revisão semanal {week}",
            timestamp=datetime.now(timezone.utc),
            **{"privacy": "local_only",
               "generated_via": "local:review",
               "source_sha256": hashlib.sha256(body.encode()).hexdigest()}))
    kb = s.path("knowledge")
    result = BundleWriter(kb).write(
        [doc], log_kind="Review",
        log_message=f"revisão semanal {week}",
        commit_message=f"review: {week}")
    emit("review.done", {"week": week, "page": doc.rel_path})
    return {"page": doc.rel_path, "commit": result["commit"], **data}
