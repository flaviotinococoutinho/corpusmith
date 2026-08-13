"""RebuildIndex — o index.db é 100% derivado; este use case é a única
porta de reconstrução (chunks, arestas, entidades, níveis, cites)."""
from __future__ import annotations
from .base import UseCase
from ..retrieval.fts import rebuild_index
from ..settings import Settings


class RebuildIndex(UseCase):
    def __init__(self, settings: Settings):
        self._settings = settings

    def execute(self) -> dict:
        return rebuild_index(self._settings)
