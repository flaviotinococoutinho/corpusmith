from __future__ import annotations
import posixpath, re
from dataclasses import dataclass

MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
WIKILINK = re.compile(r"\[\[([^\]#|]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
_EXTERNAL = ("http://", "https://", "mailto:", "urn:", "ftp://")

@dataclass
class Link:
    text: str
    target: str
    kind: str                              # "markdown" | "wikilink"

def parse_links(body: str) -> list[Link]:
    out = [Link(m.group(1), m.group(2), "markdown") for m in MD_LINK.finditer(body)]
    out += [Link(m.group(2) or m.group(1).strip(), m.group(1).strip(), "wikilink")
            for m in WIKILINK.finditer(body)]
    return out

def is_internal(target: str) -> bool:
    return not target.startswith(_EXTERNAL) and not target.startswith("#")

def resolve(target: str, from_rel: str) -> str:
    t = target.split("#")[0]
    rel = t.lstrip("/") if t.startswith("/") else posixpath.normpath(
        posixpath.join(posixpath.dirname(from_rel), t))
    return rel if rel.endswith(".md") else rel + ".md"

def md_link(title: str, rel_path: str) -> str:
    return f"[{title}](/{rel_path})"       # ÚNICO formato emitido pelo writer

def rewrite_wikilinks(body: str, resolve_title) -> str:
    def sub(m: re.Match) -> str:
        target, alias = m.group(1).strip(), m.group(2)
        rel = resolve_title(target)
        return md_link(alias or target, rel) if rel else m.group(0)
    return WIKILINK.sub(sub, body)
