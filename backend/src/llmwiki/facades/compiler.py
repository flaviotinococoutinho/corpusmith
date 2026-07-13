"""CompilerFacade — a memória em construção: compilar, indexar, agrupar,
orquestrar (pipelines configuráveis, v0.17)."""
from __future__ import annotations
from typing import Callable, Mapping
from ..settings import Settings
from ..usecases.compile_source import CompileSource
from ..usecases.consolidate_inbox import ConsolidateInbox
from ..usecases.detect_communities import DetectCommunities
from ..usecases.ingest_source import IngestSource
from ..usecases.rebuild_index import RebuildIndex
from ..usecases.run_pipeline import (DeletePipeline, RunPipeline,
                                     SavePipeline, list_pipelines,
                                     pipeline_runs, seed_default_pipelines)


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

    # ------------------------------------- pipelines configuráveis (v0.17)
    def pipelines(self) -> list[dict]:
        return list_pipelines(self._settings)

    def save_pipeline(self, name: str, spec: dict) -> dict:
        return SavePipeline(self._settings, name, spec).execute()

    def delete_pipeline(self, name: str) -> dict:
        return DeletePipeline(self._settings, name).execute()

    def run_pipeline(self, name: str, registry: Mapping[str, Callable],
                     notify=None, cancelled=None) -> dict:
        """O registry de jobs entra por injeção (DIP) — quem conhece os
        handlers é a camada adapter, nunca o domínio."""
        return RunPipeline(self._settings, name, registry, notify,
                           cancelled=cancelled).execute()

    def pipeline_runs(self, name: str | None = None,
                      limit: int = 20) -> list[dict]:
        return pipeline_runs(self._settings, name, limit)

    def seed_pipelines(self) -> None:
        seed_default_pipelines(self._settings)
