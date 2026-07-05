"""MarkPageStale — deprecia sem apagar (tempo de CÓDIGO: stale_as_of).

v0.10 (TMS — Doyle 1979): depreciar uma página propaga suspeita para quem
DEPENDE dela. Os in-links do grafo são as justificativas registradas; o
resultado lista os `dependents` para o humano revisar — propagação de
staleness, nunca invalidação em cascata automática."""
from __future__ import annotations
from .base import UseCase
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..runtime.db import connect
from ..settings import Settings


def dependents_of(settings: Settings, page: str) -> list[str]:
    """Páginas que citam `page` (justificativas apoiadas nela)."""
    idx = connect(settings.app_support / "index.db")
    rows = [r["src"] for r in idx.execute(
        "SELECT DISTINCT src FROM graph_edges WHERE dst=? AND src!=?",
        (page, page))]
    idx.close()
    return sorted(rows)


class MarkPageStale(UseCase):
    def __init__(self, settings: Settings, page_path: str):
        self._settings = settings
        self._page_path = page_path

    def execute(self) -> dict:
        writer = BundleWriter(self._settings.path("knowledge"))
        document = writer.reader.load(self._page_path)
        head = writer.git.repo.head.commit.hexsha[:12]
        meta = document.meta.model_dump(exclude_none=True)
        meta["stale_as_of"] = head
        stale = OKFDocument(rel_path=document.rel_path, body=document.body,
                            meta=OKFFrontMatter(**meta))
        result = writer.write(
            [stale], log_kind="Deprecation",
            log_message=f"marcada stale: {document.rel_path}",
            commit_message=f"stale: {document.rel_path}")
        return {**result,
                "dependents": dependents_of(self._settings, document.rel_path)}
