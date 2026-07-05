"""Job `compile_source` (v0.6 §4.2 + v0.7 §5.1 + sanduíche v0.8 §6.1):
fonte em raw/ → página OKF com proveniência completa.

O LLM fica cercado por duas passadas determinísticas:
  PRÉ  — analyze() anota entidades canônicas da fonte e o anexo entra no
         prompt ("use EXATAMENTE estas grafias");
  PÓS  — rewrite() aplica grafia canônica (só páginas de máquina), o anexo
         re-anotado vai para frontmatter/index.db, PII força local_only e o
         reconciliador decide ADD/UPDATE/SUPERSEDE/NOOP antes do writer.
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
from ..normalize import analyze
from ..okf.authorities import load_gazetteer, normalize_machine_body
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..retrieval.fts import rebuild_index
from ..runtime.db import connect
from ..settings import Settings
from . import reconcile

_SUMMARY_PROMPT = (
    "Resuma o texto a seguir como uma página de wiki de conhecimento "
    "pessoal em Markdown (sem frontmatter), com um parágrafo de abertura "
    "e seções curtas. Não invente fatos.\n"
    "Entidades canônicas detectadas na fonte (use EXATAMENTE estas "
    "grafias):\n{annex}\n\n---\n\n{text}")


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

    writer = BundleWriter(kb)
    gaz = load_gazetteer(writer.reader)

    emit("compile.extracting", {"source": rel_src})
    text = extract(src)

    # PRÉ: anexo de entidades canônicas no prompt (teto de custo em fontes enormes)
    pre = analyze(text[:200_000], gaz=gaz)
    annex = "\n".join(sorted({m.canonical for m in pre.matches
                              if m.kind in ("entity", "standard")}))[:2_000]

    via = "local:compile"
    body = text.strip()
    try:
        router = ModelRouter(s)
        result = router.complete(
            _SUMMARY_PROMPT.format(annex=annex or "(nenhuma)",
                                   text=text[:24_000]),
            privacy=privacy, max_tokens=2048)
        body, via = result["text"].strip(), result["via"]
    except (ModelUnavailable, Exception):
        router = None
        via = "local:compile"

    title = src.stem.replace("-", " ").replace("_", " ").strip()
    now = datetime.now(timezone.utc)

    # PÓS: grafia canônica + anexo re-anotado sobre o texto final
    if not body.lstrip().startswith("# "):
        body = f"# {title}\n\n{body}"
    full_body, rep = normalize_machine_body(body + "\n", gaz)
    extra = {"privacy": privacy,
             "generated_via": via,
             "source": rel_src,
             "source_sha256": sha}
    if rep.sensitive:                       # PII ⇒ LGPD topológica (§4.3)
        extra["privacy"] = "local_only"
        extra["sensitive_data"] = True
    doc = OKFDocument(
        rel_path=f"concepts/{_slug(src.stem)}.md",
        body=full_body,
        meta=OKFFrontMatter(
            type="concept", title=title,
            timestamp=now, valid_at=now,
            entities=rep.entities_frontmatter() or None,
            **extra))

    # reconciliação ADD/UPDATE/SUPERSEDE/NOOP (§5) — sempre logada
    decision = reconcile.plan(s, doc, rep, router)
    reconcile.log(s, doc.rel_path, decision)
    if decision["op"] == "NOOP":
        emit("compile.noop", {"source": rel_src, "reason": decision["reason"]})
        return {"page": None, "op": "NOOP", "via": via}
    if decision["op"] == "UPDATE":
        doc.rel_path = decision["target"]
    if decision["op"] == "SUPERSEDE":
        old = writer.reader.load(decision["target"])
        old_meta = old.meta.model_dump(exclude_none=True)
        old_meta.update(superseded_by=doc.rel_path, invalid_at=now)
        superseded = OKFDocument(rel_path=old.rel_path, body=old.body,
                                 meta=OKFFrontMatter(**old_meta))
        writer.write([superseded], log_kind="Deprecation",
                     log_message=f"supersedida por {doc.rel_path}",
                     commit_message=f"supersede: {old.rel_path}")

    result = writer.write(
        [doc], log_kind="Creation" if decision["op"] == "ADD" else "Update",
        log_message=f"compilado de {rel_src} ({decision['op']})",
        commit_message=f"compile({decision['op'].lower()}): {rel_src}")

    rt = connect(s.app_support / "runtime.db")
    rt.execute("INSERT OR REPLACE INTO compile_cache(source,sha,at) "
               "VALUES (?,?,?)", (rel_src, sha, time.time()))
    rt.commit()
    rt.close()
    rebuild_index(s)
    emit("compile.done", {"source": rel_src, "page": doc.rel_path,
                          "op": decision["op"]})
    return {"page": doc.rel_path, "via": via, "op": decision["op"],
            "commit": result["commit"]}
