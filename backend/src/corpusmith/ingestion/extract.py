"""Extração de texto de fontes raw/ (v0.6 §4.1).

Markdown/TXT são lidos direto. PDF/EPUB dependem de parsers AGPL
(pymupdf4llm, ebooklib) que ficam FORA do binário distribuído (§8.1):
rodam pelo Python do venv em subprocesso, instalados via extra
`corpusmith[parsers]`.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path


class ExtractError(RuntimeError):
    pass


_PDF_SNIPPET = """
import json, sys
import pymupdf4llm
print(json.dumps({"text": pymupdf4llm.to_markdown(sys.argv[1])}))
"""

_EPUB_SNIPPET = """
import json, sys, html, re
from ebooklib import epub, ITEM_DOCUMENT
book = epub.read_epub(sys.argv[1])
parts = []
for item in book.get_items_of_type(ITEM_DOCUMENT):
    t = item.get_content().decode("utf-8", "ignore")
    t = re.sub(r"<[^>]+>", " ", t)
    parts.append(html.unescape(t))
print(json.dumps({"text": "\\n\\n".join(parts)}))
"""


def extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(errors="ignore")
    if suffix == ".pdf":
        return _subprocess_extract(_PDF_SNIPPET, path)
    if suffix == ".epub":
        return _subprocess_extract(_EPUB_SNIPPET, path)
    raise ExtractError(f"formato não suportado: {suffix}")


def _subprocess_extract(snippet: str, path: Path) -> str:
    proc = subprocess.run([sys.executable, "-c", snippet, str(path)],
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise ExtractError(
            f"parser falhou para {path.name} (extra [parsers] instalado?): "
            + proc.stderr.strip()[-500:])
    return json.loads(proc.stdout)["text"]
