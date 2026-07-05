"""Job `compile_source` (v0.6 §4.2 + patch v0.7 §5.1): fonte em raw/ →
página OKF em concepts/, com proveniência completa.

Página compilada é gerada por MÁQUINA: `generated_via: local:compile`
(ou api:* quando o roteador usa API), portanto `source_sha256` é
OBRIGATÓRIO (policy.source_sha_required). `timestamp` é datetime real —
nunca string arbitrária.
"""
from __future__ import annotations
import hashlib
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from ..ingestion.extract import extract
from ..models.router import ModelRouter, ModelUnavailable
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..retrieval.fts import rebuild_index
from ..runtime.db import connect
from ..settings import Settings

_SUMMARY_PROMPT = (
    "Resuma o texto a seguir como uma página de wiki de conhecimento "
    "pessoal em Markdown (sem frontmatter), com um parágrafo de abertura "
    "e seções curtas. Não invente fatos.\n\n---\n\n{text}")


def _slug(name: str) -> str:
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "sem-titulo"


def run(s: Settings, payload: dict, emit) -> dict:
    kb = s.path("knowledge")
    src = Path(payload["path"])
    if not src.is_absolute():
        src = kb / payload["path"]
    if not src.is_file():
        raise FileNotFoundError(f"fonte inexistente: {src}")
    rel_src = str(src.relative_to(kb)) if src.is_relative_to(kb) else src.name
    privacy = s.resolve_privacy(rel_src)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()

    emit("compile.extracting", {"source": rel_src})
    text = extract(src)

    via = "local:compile"
    body = text.strip()
    try:
        router = ModelRouter(s)
        result = router.complete(_SUMMARY_PROMPT.format(text=text[:24_000]),
                                 privacy=privacy, max_tokens=2048)
        body, via = result["text"].strip(), result["via"]
    except (ModelUnavailable, Exception):
        # sem modelo: compila extrativo (o conteúdo original vira a página)
        via = "local:compile"

    title = src.stem.replace("-", " ").replace("_", " ").strip()
    doc = OKFDocument(
        rel_path=f"concepts/{_slug(src.stem)}.md",
        body=f"# {title}\n\n{body}\n",
        meta=OKFFrontMatter(
            type="concept", title=title,
            timestamp=datetime.now(timezone.utc),
            **{"privacy": privacy,
               "generated_via": via,
               "source": rel_src,
               "source_sha256": sha}))
    result = BundleWriter(kb).write(
        [doc], log_kind="Creation",
        log_message=f"compilado de {rel_src}",
        commit_message=f"compile: {rel_src}")

    rt = connect(s.app_support / "runtime.db")
    rt.execute("INSERT OR REPLACE INTO compile_cache(source,sha,at) "
               "VALUES (?,?,?)", (rel_src, sha, time.time()))
    rt.commit()
    rt.close()
    rebuild_index(s)
    emit("compile.done", {"source": rel_src, "page": doc.rel_path})
    return {"page": doc.rel_path, "via": via, **{"commit": result["commit"]}}
