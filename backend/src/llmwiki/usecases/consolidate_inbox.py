"""ConsolidateInbox — consolidação por recorrência (CLS, v0.10).

McClelland, McNaughton & O'Reilly, "Why there are complementary learning
systems in the hippocampus and neocortex" (Psychological Review, 1995):
codificação rápida barata + consolidação lenta que extrai estrutura.
Transposição local-first: `raw/` é o hipocampo (captura sem custo de
modelo); a consolidação neocortical SÓ dispara quando há RECORRÊNCIA —
e a recorrência é detectada DETERMINISTICAMENTE, sem embeddings:

  duas fontes pendentes convergem se compartilham um identificador forte
  (DOI/ISBN/arXiv/ISSN) OU ≥ `min_shared` entidades/normas canônicas
  (o anexo do normalize já dá a assinatura de graça).

Cada cluster gera UMA chamada de LLM (não uma por nota) via o MESMO
Template Method de página de máquina — sanduíche, reconciliação e gate
inclusos. Fontes fora de cluster ficam pendentes (o compile individual
continua disponível); nada é descartado — Git e raw/ são o backstop.
"""
from __future__ import annotations
import hashlib
import time
from pathlib import Path
from .base import DraftPage, MachinePageUseCase, UseCase
from .compile_source import _slug
from .reconcile_candidate import ReconcileCandidate, log_decision
from ..ingestion.extract import ExtractError, extract
from ..kernel.sketch import hamming, simhash
from ..models.router import ModelRouter, ModelUnavailable
from ..normalize import analyze
from ..okf.authorities import load_gazetteer
from ..okf.bundle import BundleReader
from ..retrieval.fts import rebuild_index
from ..runtime.db import connect
from ..settings import Settings

SOURCE_SUFFIXES = {".md", ".txt", ".pdf", ".epub"}
STRONG_IDS = ("doi", "isbn", "issn", "arxiv")

_PROMPT = (
    "As notas a seguir tratam do MESMO tema. Sintetize-as numa única "
    "página de wiki em Markdown (sem frontmatter): um parágrafo de "
    "abertura e seções curtas, eliminando redundâncias sem perder fatos. "
    "Não invente nada.\nEntidades canônicas (use EXATAMENTE estas "
    "grafias):\n{annex}\n\n---\n\n{notes}")


class _Signature:
    """Assinatura determinística de recorrência de uma fonte pendente:
    ids fortes + entidades canônicas + sketch SimHash (near-duplicata)."""

    NEAR_DUPLICATE_HAMMING = 8

    def __init__(self, relative: str, text: str, gazetteer):
        report = analyze(text[:100_000], gaz=gazetteer)
        self.relative = relative
        self.text = text
        self.sketch = simhash(text[:100_000])
        self.strong_ids = {m.canonical for m in report.matches
                           if m.kind == "identifier"
                           and m.subkind in STRONG_IDS
                           and m.valid is not False}
        self.entities = {m.canonical for m in report.matches
                         if m.kind in ("entity", "standard")
                         and m.confidence != "ambiguous"}

    def converges_with(self, other: "_Signature", min_shared: int) -> bool:
        if self.strong_ids & other.strong_ids:
            return True
        if hamming(self.sketch, other.sketch) <= self.NEAR_DUPLICATE_HAMMING:
            return True                      # quase-cópias sempre convergem
        return len(self.entities & other.entities) >= min_shared


class _ConsolidatedPage(MachinePageUseCase):
    """Uma página por cluster — herda TODO o esqueleto (sanduíche →
    reconcile → gate → writer); aqui só a produção do rascunho."""

    def __init__(self, settings: Settings, cluster: list[_Signature],
                 notify=None):
        super().__init__(settings, notify)
        self._cluster = cluster
        self._via = "local:consolidate"
        self._router: ModelRouter | None = ModelRouter(settings)

    def _produce(self) -> DraftPage:
        shared = set.intersection(*(s.entities for s in self._cluster)) \
            if len(self._cluster) > 1 else set()
        topic = sorted(shared)[0] if shared \
            else Path(self._cluster[0].relative).stem
        annex = "\n".join(sorted(set.union(
            *(s.entities for s in self._cluster))))[:2_000]
        notes = "\n\n---\n\n".join(
            f"[fonte: {s.relative}]\n{s.text[:12_000]}"
            for s in self._cluster)
        body = "\n\n".join(f"## Fonte: {s.relative}\n\n{s.text.strip()}"
                           for s in self._cluster)
        try:
            result = self._router.complete(
                _PROMPT.format(annex=annex or "(nenhuma)", notes=notes),
                privacy=self._privacy(), max_tokens=2048)
            body, self._via = result["text"].strip(), result["via"]
        except (ModelUnavailable, Exception):
            self._router = None
        title = topic if shared else topic.replace("-", " ")
        if not body.lstrip().startswith("# "):
            body = f"# {title}\n\n{body}"
        fingerprint = hashlib.sha256("\n".join(sorted(
            hashlib.sha256(s.text.encode()).hexdigest()
            for s in self._cluster)).encode()).hexdigest()
        return DraftPage(
            rel_path=f"concepts/{_slug(title)}.md",
            title=title, body=body + "\n",
            meta={"privacy": self._privacy(), "generated_via": self._via,
                  "sources": [s.relative for s in self._cluster],
                  "source_sha256": fingerprint},
            log_message="consolidado de "
                        + ", ".join(s.relative for s in self._cluster),
            commit_message=f"consolidate: {_slug(title)}")

    def _privacy(self) -> str:
        levels = {self._settings.resolve_privacy(s.relative)
                  for s in self._cluster}
        return "local_only" if "local_only" in levels else "api_allowed"

    def _reconcile(self, document, report) -> dict:
        decision = ReconcileCandidate(self._settings, document, report,
                                      self._router).execute()
        log_decision(self._settings, document.rel_path, decision)
        return decision

    def _after_write(self, document, report) -> None:
        rt = connect(self._settings.app_support / "runtime.db")
        now = time.time()
        for signature in self._cluster:
            rt.execute("INSERT OR REPLACE INTO compile_cache(source,sha,at,page) "
                       "VALUES (?,?,?,?)",
                       (signature.relative,
                        hashlib.sha256(signature.text.encode()).hexdigest(),
                        now, document.rel_path))
        rt.commit()
        rt.close()
        rebuild_index(self._settings)
        self._notify("consolidate.done",
                     {"page": document.rel_path,
                      "sources": [s.relative for s in self._cluster]})


class ConsolidateInbox(UseCase):
    def __init__(self, settings: Settings, notify=None, *,
                 min_shared: int = 2, min_cluster: int = 2):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)
        self._min_shared = min_shared
        self._min_cluster = min_cluster

    def execute(self) -> dict:
        pending = self._pending_signatures()
        clusters = self._cluster(pending)
        pages = []
        for cluster in clusters:
            result = _ConsolidatedPage(self._settings, cluster,
                                       self._notify).execute()
            if result.get("page"):
                pages.append(result["page"])
        consolidated = {s.relative for c in clusters for s in c}
        return {"pending": len(pending), "clusters": len(clusters),
                "pages": pages,
                "left": sorted(s.relative for s in pending
                               if s.relative not in consolidated)}

    def _pending_signatures(self) -> list[_Signature]:
        kb = self._settings.path("knowledge")
        gazetteer = load_gazetteer(BundleReader(kb / "bundle"))
        rt = connect(self._settings.app_support / "runtime.db")
        cache = {r["source"]: r["sha"] for r in
                 rt.execute("SELECT source, sha FROM compile_cache")}
        rt.close()
        out: list[_Signature] = []
        for path in sorted((kb / "raw").rglob("*")):
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            relative = str(path.relative_to(kb))
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if cache.get(relative) == sha:
                continue                             # já consolidada/compilada
            try:
                out.append(_Signature(relative, extract(path), gazetteer))
            except ExtractError:
                continue                             # parser ausente: fica
        return out

    def _cluster(self, pending: list[_Signature]) -> list[list[_Signature]]:
        parent = list(range(len(pending)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(pending)):
            for j in range(i + 1, len(pending)):
                if pending[i].converges_with(pending[j], self._min_shared):
                    parent[find(i)] = find(j)
        groups: dict[int, list[_Signature]] = {}
        for i, signature in enumerate(pending):
            groups.setdefault(find(i), []).append(signature)
        return [g for g in groups.values() if len(g) >= self._min_cluster]
