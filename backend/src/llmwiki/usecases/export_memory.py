"""ExportMemory (Fase 5) — o exportador INTELIGENTE.

"Inteligente" tem significado preciso aqui: o export respeita a
privacidade por default (páginas `local_only` FICAM DE FORA a menos que
o humano peça explicitamente), filtra por tipo/tag, carrega proveniência
(manifesto com origem, sha e commit do HEAD) e sai em três formatos:

  zip   — as páginas .md como estão + manifest.json (interoperável OKF)
  json  — [{path, meta, body}] para pipelines
  md    — digest único com sumário e separadores (leitura/colagem)
"""
from __future__ import annotations
import io
import json
import time
import zipfile
from .base import UseCase
from ..okf.bundle import BundleReader
from ..okf.git_store import GitStore
from ..settings import Settings

FORMATS = ("zip", "json", "md")


class ExportMemory(UseCase):
    def __init__(self, settings: Settings, *, format: str = "zip",
                 include_local: bool = False, types: list[str] | None = None,
                 tag: str | None = None):
        if format not in FORMATS:
            raise ValueError(f"formato inválido: {format} "
                             f"(aceitos: {FORMATS})")
        self._settings = settings
        self._format = format
        self._include_local = include_local
        self._types = set(types or [])
        self._tag = tag

    def execute(self) -> dict:
        kb = self._settings.path("knowledge")
        reader = BundleReader(kb / "bundle")
        head = GitStore(kb).head()
        selected = []
        excluded_private = 0
        for d in reader.iter_concepts():
            x = d.meta.model_dump(exclude_none=True, mode="json")
            if x.get("privacy") == "local_only" and not self._include_local:
                excluded_private += 1
                continue
            if self._types and d.meta.type not in self._types:
                continue
            if self._tag and self._tag not in d.meta.tags:
                continue
            selected.append((d, x))
        manifest = {"exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "kb_head": head, "pages": len(selected),
                    "excluded_local_only": excluded_private,
                    "filters": {"types": sorted(self._types) or None,
                                "tag": self._tag,
                                "include_local": self._include_local}}
        builder = {"zip": self._zip, "json": self._json, "md": self._md}
        content, media, ext = builder[self._format](selected, manifest)
        stamp = time.strftime("%Y%m%d-%H%M")
        return {"content": content, "media_type": media,
                "filename": f"llmwiki-export-{stamp}.{ext}",
                "manifest": manifest}

    def _zip(self, selected, manifest):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            for d, _x in selected:
                zf.writestr(f"bundle/{d.rel_path}", d.dumps())
        return buffer.getvalue(), "application/zip", "zip"

    def _json(self, selected, manifest):
        payload = {"manifest": manifest,
                   "pages": [{"path": d.rel_path, "meta": x, "body": d.body}
                             for d, x in selected]}
        return (json.dumps(payload, ensure_ascii=False, indent=2).encode(),
                "application/json", "json")

    def _md(self, selected, manifest):
        lines = [f"# Export LLM Wiki — {manifest['exported_at']}",
                 f"\n{manifest['pages']} página(s) · HEAD {manifest['kb_head'] or '—'}"
                 + (f" · {manifest['excluded_local_only']} privada(s) omitida(s)"
                    if manifest["excluded_local_only"] else ""), "\n## Sumário\n"]
        lines += [f"- [{d.meta.title or d.rel_path}](#{d.concept_id})"
                  for d, _ in selected]
        for d, x in selected:
            lines += [f"\n---\n\n<!-- {d.rel_path} · {x.get('generated_via', '')}"
                      f" · {x.get('source_sha256', '')[:12]} -->",
                      d.body.strip()]
        return "\n".join(lines).encode(), "text/markdown", "md"
