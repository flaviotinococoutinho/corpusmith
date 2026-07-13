"""CompileSource — subclasse do Template Method (v0.9): só os hooks.

O esqueleto (sanduíche PÓS + reconciliação + gate + writer) é herdado e
imutável; aqui vive apenas o que é ESPECÍFICO de compilar uma fonte raw/:
extração, anexo PRÉ no prompt, proveniência (source_sha256) e o pós-escrita
(compile_cache + reindex).
"""
from __future__ import annotations
import hashlib
import re
import time
import unicodedata
from pathlib import Path
from .base import DraftPage, MachinePageUseCase
from .reconcile_candidate import ReconcileCandidate, log_decision
from ..ingestion.extract import extract
from ..models.router import ModelRouter, ModelUnavailable
from ..normalize import analyze
from ..retrieval.fts import rebuild_index
from ..runtime.db import connect
from ..settings import Settings

_SUMMARY_PROMPT = (
    "Resuma o texto a seguir como uma página de wiki de conhecimento "
    "pessoal em Markdown (sem frontmatter), com um parágrafo de abertura "
    "e seções curtas. Não invente fatos.\n"
    "Entidades canônicas detectadas na fonte (use EXATAMENTE estas "
    "grafias):\n{annex}\n\n---\n\n{text}")


def _slug(name: str) -> str:
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "sem-titulo"


class CompileSource(MachinePageUseCase):
    def __init__(self, settings: Settings, source_path: str, notify=None):
        super().__init__(settings, notify)
        kb = settings.path("knowledge")
        source = Path(source_path)
        self._source = source if source.is_absolute() else kb / source_path
        self._relative_source = (str(self._source.relative_to(kb))
                                 if self._source.is_relative_to(kb)
                                 else self._source.name)
        self._via = "local:compile"
        self._router: ModelRouter | None = ModelRouter(settings)
        self._sha = ""

    # -------------------------------------------------------------- hooks
    def _produce(self) -> DraftPage:
        # idempotência (v1.2, auditoria D-6): fonte com o MESMO sha do
        # compile_cache já foi compilada — SKIP sem custo de modelo
        import hashlib as _hl
        from ..runtime.db import connect as _connect
        if self._source.exists():
            _sha = _hl.sha256(self._source.read_bytes()).hexdigest()
            _rt = _connect(self._settings.app_support / "runtime.db")
            _row = _rt.execute("SELECT sha FROM compile_cache WHERE source=?",
                               (self._relative_source,)).fetchone()
            _rt.close()
            if _row and _row["sha"] == _sha:
                return None
        if not self._source.is_file():
            raise FileNotFoundError(f"fonte inexistente: {self._source}")
        self._sha = hashlib.sha256(self._source.read_bytes()).hexdigest()
        privacy = self._settings.resolve_privacy(self._relative_source)
        self._notify("compile.extracting", {"source": self._relative_source})
        text = extract(self._source)

        # PRÉ: anexo de entidades canônicas no prompt (teto em fontes enormes)
        pre = analyze(text[:200_000], gaz=self._gazetteer)
        annex = "\n".join(sorted({m.canonical for m in pre.matches
                                  if m.kind in ("entity", "standard")}))[:2_000]
        body = text.strip()
        try:
            result = self._router.complete(
                _SUMMARY_PROMPT.format(annex=annex or "(nenhuma)",
                                       text=text[:24_000]),
                privacy=privacy, max_tokens=2048)
            body, self._via = result["text"].strip(), result["via"]
        except (ModelUnavailable, Exception):
            self._router = None

        title = self._source.stem.replace("-", " ").replace("_", " ").strip()
        if not body.lstrip().startswith("# "):
            body = f"# {title}\n\n{body}"
        return DraftPage(
            rel_path=f"concepts/{_slug(self._source.stem)}.md",
            title=title, body=body + "\n",
            meta={"privacy": privacy, "generated_via": self._via,
                  "source": self._relative_source, "source_sha256": self._sha},
            log_message=f"compilado de {self._relative_source}",
            commit_message=f"compile: {self._relative_source}")

    def _reconcile(self, document, report) -> dict:
        decision = ReconcileCandidate(self._settings, document, report,
                                      self._router).execute()
        log_decision(self._settings, document.rel_path, decision)
        return decision

    def _after_write(self, document, report) -> None:
        rt = connect(self._settings.app_support / "runtime.db")
        rt.execute("INSERT OR REPLACE INTO compile_cache(source,sha,at,page) "
                   "VALUES (?,?,?,?)",
                   (self._relative_source, self._sha, time.time(),
                    document.rel_path))
        rt.commit()
        rt.close()
        rebuild_index(self._settings)
        self._notify("compile.done", {"source": self._relative_source,
                                      "page": document.rel_path})

    def _extra_result(self) -> dict:
        return {"via": self._via}
