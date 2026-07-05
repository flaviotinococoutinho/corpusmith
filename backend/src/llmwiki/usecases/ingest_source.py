"""IngestSource (v0.11) — a porta de ENTRADA do conhecimento pelo app.

Até aqui o inbox só enxergava arquivos que chegavam por fora (filesystem).
Este use case recebe conteúdo do Cockpit (upload, nota rápida, correção)
e o materializa em `raw/` — o hipocampo do sistema (CLS): captura barata,
sem modelo, imediatamente visível no Inbox e elegível para compile
individual ou consolidação por recorrência.

Regras: só sufixos suportados pela extração; nome slugificado; colisão
nunca sobrescreve (sufixo -2, -3, …); binário via base64.
"""
from __future__ import annotations
import base64
import re
import unicodedata
from pathlib import Path
from .base import UseCase
from ..settings import Settings

SAFE_SUFFIXES = {".md", ".txt", ".pdf", ".epub"}


def _slug(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode(
        "ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:60] or "nota"


class IngestSource(UseCase):
    def __init__(self, settings: Settings, *, filename: str,
                 content: str | None = None,
                 content_base64: str | None = None,
                 subdir: str | None = None):
        suffix = Path(filename).suffix.lower()
        if suffix not in SAFE_SUFFIXES:
            raise ValueError(f"sufixo não suportado: {suffix or '(nenhum)'} "
                             f"(aceitos: {sorted(SAFE_SUFFIXES)})")
        if content is None and content_base64 is None:
            raise ValueError("content ou content_base64 é obrigatório")
        self._settings = settings
        self._stem = _slug(Path(filename).stem)
        self._suffix = suffix
        self._content = content
        self._content_base64 = content_base64
        self._subdir = _slug(subdir) if subdir else None

    def execute(self) -> dict:
        kb = self._settings.path("knowledge")
        target_dir = kb / "raw" / self._subdir if self._subdir else kb / "raw"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = self._free_path(target_dir)
        if self._content is not None:
            target.write_text(self._content)
        else:
            target.write_bytes(base64.b64decode(self._content_base64))
        relative = str(target.relative_to(kb))
        return {"path": relative,
                "privacy": self._settings.resolve_privacy(relative),
                "bytes": target.stat().st_size}

    def _free_path(self, target_dir: Path) -> Path:
        candidate = target_dir / f"{self._stem}{self._suffix}"
        counter = 2
        while candidate.exists():
            candidate = target_dir / f"{self._stem}-{counter}{self._suffix}"
            counter += 1
        return candidate
