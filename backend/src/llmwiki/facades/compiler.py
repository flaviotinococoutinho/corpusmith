"""CompilerFacade — a memória em construção: compilar, indexar, agrupar."""
from __future__ import annotations
from ..settings import Settings
from ..usecases.compile_source import CompileSource
from ..usecases.consolidate_inbox import ConsolidateInbox
from ..usecases.detect_communities import DetectCommunities
from ..usecases.ingest_source import IngestSource
from ..usecases.rebuild_index import RebuildIndex


class CompilerFacade:
    def __init__(self, settings: Settings):
        self._settings = settings

    def ingest(self, *, filename: str, content: str | None = None,
               content_base64: str | None = None,
               subdir: str | None = None) -> dict:
        """Entrada de conhecimento pelo app: conteúdo → raw/ (inbox)."""
        return IngestSource(self._settings, filename=filename,
                            content=content, content_base64=content_base64,
                            subdir=subdir).execute()

    def compile(self, source_path: str, notify=None) -> dict:
        return CompileSource(self._settings, source_path, notify).execute()

    def consolidate_inbox(self, notify=None) -> dict:
        """CLS: uma chamada de LLM por CLUSTER recorrente, não por nota."""
        return ConsolidateInbox(self._settings, notify).execute()

    def rebuild_index(self) -> dict:
        return RebuildIndex(self._settings).execute()

    def detect_communities(self, notify=None) -> dict:
        return DetectCommunities(self._settings, notify).execute()
