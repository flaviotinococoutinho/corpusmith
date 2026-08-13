from __future__ import annotations
import re
import frontmatter as fm
from pathlib import Path
from .findings import Finding
from ..okf.document import OKFDocument, is_reserved
from ..okf.links import parse_links, is_internal, resolve

DATE_H = re.compile(r"^## \d{4}-\d{2}-\d{2}\s*$")

def check(docs: list[OKFDocument], reader) -> list[Finding]:
    """Só o SPEC. Tipos desconhecidos, chaves extras, campos opcionais
    ausentes e AUSÊNCIA de # Citations não geram finding algum
    (citações são SHOULD — exigi-las é política local, §4.3)."""
    out: list[Finding] = []
    incoming = {d.rel_path for d in docs}
    for d in docs:
        for link in parse_links(d.body):
            if not is_internal(link.target):
                continue
            rel = resolve(link.target, d.rel_path)
            if rel not in incoming and not reader.exists(rel):
                out.append(Finding("warn", "okf.broken_link", d.rel_path,
                                   f"alvo inexistente: {link.target} "
                                   "(pode ser conhecimento futuro)",
                                   okf_conformance=True, meta={"target": rel}))
    return out

def check_reserved_files(bundle_root: Path) -> list[Finding]:
    """Reservados são validados QUANDO PRESENTES; ausência nunca invalida."""
    out: list[Finding] = []
    log = bundle_root / "log.md"
    if log.exists():
        bad = [h for h in log.read_text().splitlines()
               if h.startswith("## ") and not DATE_H.match(h)]
        if bad:
            out.append(Finding("warn", "okf.log_heading", "log.md",
                               f"headings não-ISO: {bad[:3]}", okf_conformance=True))
    for idx in bundle_root.rglob("index.md"):
        post = fm.loads(idx.read_text())
        extra = set(post.metadata) - {"okf_version"}
        if post.metadata and (idx.parent != bundle_root or extra):
            out.append(Finding("warn", "okf.reserved_frontmatter",
                               str(idx.relative_to(bundle_root)),
                               "index.md não deve ter frontmatter "
                               "(exceto okf_version no raiz)", okf_conformance=True))
    return out
