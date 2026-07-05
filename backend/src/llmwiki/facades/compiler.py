"""CompilerFacade — a memória em construção: compilar, indexar, agrupar."""
from __future__ import annotations
from ..settings import Settings
from ..usecases.compile_source import CompileSource
from ..usecases.detect_communities import DetectCommunities
from ..usecases.rebuild_index import RebuildIndex


class CompilerFacade:
    def __init__(self, settings: Settings):
        self._settings = settings

    def compile(self, source_path: str, notify=None) -> dict:
        return CompileSource(self._settings, source_path, notify).execute()

    def rebuild_index(self) -> dict:
        return RebuildIndex(self._settings).execute()

    def detect_communities(self, notify=None) -> dict:
        return DetectCommunities(self._settings, notify).execute()
