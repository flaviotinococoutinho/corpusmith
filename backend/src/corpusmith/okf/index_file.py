"""Geração dos `index.md` reservados (v0.6 §2.3).

Regras do SPEC respeitadas pela conformidade (§4.2 v0.7):
- `index.md` de subdiretório NÃO tem frontmatter;
- `index.md` da raiz pode ter APENAS `okf_version`;
- ausência de index.md nunca invalida o bundle — a geração aqui é serviço
  do writer, não exigência.
"""
from __future__ import annotations
import posixpath
from pathlib import Path
from .document import RESERVED

OKF_VERSION = "0.1"


def _entries(dir_path: Path, bundle_root: Path) -> list[str]:
    lines: list[str] = []
    subdirs = sorted(p for p in dir_path.iterdir()
                     if p.is_dir() and not p.name.startswith("."))
    pages = sorted(p for p in dir_path.glob("*.md") if p.name not in RESERVED)
    for d in subdirs:
        rel = posixpath.join(str(d.relative_to(bundle_root)), "index.md")
        lines.append(f"- [{d.name}/](/{rel})")
    for p in pages:
        rel = str(p.relative_to(bundle_root))
        title = p.stem.replace("-", " ")
        lines.append(f"- [{title}](/{rel})")
    return lines


def regenerate(bundle_root: Path, rel_dir: str) -> None:
    """Reescreve o index.md de UM diretório (e nunca inventa frontmatter)."""
    dir_path = (bundle_root / rel_dir) if rel_dir else bundle_root
    if not dir_path.is_dir():
        return
    name = dir_path.name if rel_dir else "Bundle"
    body = f"# {name}\n\n" + "\n".join(_entries(dir_path, bundle_root)) + "\n"
    if dir_path == bundle_root:
        text = f"---\nokf_version: \"{OKF_VERSION}\"\n---\n\n{body}"
    else:
        text = body
    (dir_path / "index.md").write_text(text)


def regenerate_for(bundle_root: Path, rel_dirs: set[str]) -> None:
    """Regenera os index.md dos diretórios tocados + toda a cadeia de
    ancestrais até a raiz (a raiz lista os subdiretórios novos)."""
    todo: set[str] = set()
    for rel in rel_dirs:
        parts = [p for p in rel.split("/") if p]
        for i in range(len(parts) + 1):
            todo.add("/".join(parts[:i]))
    for rel in sorted(todo):
        regenerate(bundle_root, rel)
