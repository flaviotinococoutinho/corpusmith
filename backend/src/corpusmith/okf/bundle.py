from __future__ import annotations
from pathlib import Path
from typing import Iterator
from .document import OKFDocument, is_reserved

class BundleReader:
    def __init__(self, root: Path):
        self.root = root

    def exists(self, rel_path: str) -> bool:
        return (self.root / rel_path).is_file()

    def load(self, rel_path: str) -> OKFDocument:
        return OKFDocument.loads(rel_path, (self.root / rel_path).read_text())

    def raw_md_files(self) -> Iterator[str]:
        """Todos os .md não-reservados, SEM parsear — insumo do lint."""
        for p in sorted(self.root.rglob("*.md")):
            rel = str(p.relative_to(self.root))
            if not is_reserved(p.name) and not rel.startswith("reviews/"):
                yield rel

    def iter_concepts(self, strict: bool = False) -> Iterator[OKFDocument]:
        """Runtime tolera páginas malformadas (aparecem no lint, não aqui);
        strict=True propaga a exceção — para pipelines que exigem sanidade."""
        for rel in self.raw_md_files():
            try:
                yield self.load(rel)
            except Exception:
                if strict:
                    raise

    def title_index(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for d in self.iter_concepts():
            for key in filter(None, {d.meta.title, Path(d.rel_path).stem}):
                out.setdefault(key.strip().lower(), d.rel_path)
        return out
