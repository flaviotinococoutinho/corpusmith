"""MarkPageStale — deprecia sem apagar (tempo de CÓDIGO: stale_as_of)."""
from __future__ import annotations
from .base import UseCase
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..settings import Settings


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
        return writer.write([stale], log_kind="Deprecation",
                            log_message=f"marcada stale: {document.rel_path}",
                            commit_message=f"stale: {document.rel_path}")
