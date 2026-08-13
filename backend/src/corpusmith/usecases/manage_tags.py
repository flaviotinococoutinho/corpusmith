"""RenameTag (Fase 5) — o gerenciador de tags como operação de curadoria:
renomear (novo nome), fundir (nome já existente) ou remover (new=None).
Toda página afetada é reescrita NUM único write (um commit, uma entrada
de log) pelo caminho normal do writer; o índice reindexa incremental."""
from __future__ import annotations
from .base import UseCase
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..retrieval.fts import rebuild_index
from ..settings import Settings


class RenameTag(UseCase):
    def __init__(self, settings: Settings, old: str, new: str | None = None):
        if not old:
            raise ValueError("tag de origem é obrigatória")
        self._settings = settings
        self._old = old
        self._new = (new or "").strip() or None

    def execute(self) -> dict:
        writer = BundleWriter(self._settings.path("knowledge"))
        updated: list[OKFDocument] = []
        for d in writer.reader.iter_concepts():
            if self._old not in d.meta.tags:
                continue
            tags = [t for t in d.meta.tags if t != self._old]
            if self._new and self._new not in tags:
                tags.append(self._new)
            meta = d.meta.model_dump(exclude_none=True)
            meta["tags"] = tags
            updated.append(OKFDocument(rel_path=d.rel_path, body=d.body,
                                       meta=OKFFrontMatter(**meta)))
        if not updated:
            return {"pages": 0, "op": "noop"}
        op = "remove" if self._new is None else "rename"
        target = self._new or "(removida)"
        writer.write(updated, log_kind="Update",
                     log_message=f"tag {self._old} → {target} "
                                 f"({len(updated)} página(s))",
                     commit_message=f"tag: {self._old} -> {target}")
        rebuild_index(self._settings)
        return {"pages": len(updated), "op": op,
                "from": self._old, "to": self._new}
