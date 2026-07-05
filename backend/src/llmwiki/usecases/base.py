"""Contratos da camada de aplicação (v0.9).

`UseCase`: um método público por caso de uso (Object Calisthenics /
Interface Segregation) — a intenção cabe no nome da classe, não em qual
método você chamou.

`MachinePageUseCase`: Template Method (GoF) — o esqueleto de QUALQUER
escrita de página gerada por máquina é IMUTÁVEL e mora aqui:

    _produce → sanduíche (rewrite+re-annotate) → _document → _reconcile
             → aplica ADD/UPDATE/SUPERSEDE/NOOP → gate do Harness/writer
             → _after_write

Subclasses (compile, revisão semanal, sumário de comunidade) preenchem só
os hooks protegidos. Assim o invariante epistêmico (nenhuma página de
máquina entra sem normalização + reconciliação + gate) não depende de cada
job lembrar de chamá-lo — é estruturalmente impossível pular (OCP/LSP).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ..okf.authorities import load_gazetteer, normalize_machine_body
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..settings import Settings


class UseCase(ABC):
    @abstractmethod
    def execute(self):
        """Única porta de entrada do caso de uso."""


@dataclass
class DraftPage:
    """Produto do hook _produce: o rascunho ANTES do sanduíche."""
    rel_path: str
    title: str
    body: str
    meta: dict = field(default_factory=dict)
    log_message: str = ""
    commit_message: str = ""


class MachinePageUseCase(UseCase):
    LOG_KIND = "Creation"

    def __init__(self, settings: Settings, notify=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)
        self._writer = BundleWriter(settings.path("knowledge"))
        self._gazetteer = load_gazetteer(self._writer.reader)

    # ------------------------------------------------- esqueleto IMUTÁVEL
    def execute(self) -> dict:
        draft = self._produce()
        if draft is None:
            return {"op": "SKIP", "page": None, **self._extra_result()}
        body, report = normalize_machine_body(draft.body, self._gazetteer)
        document = self._document(draft, body, report)
        decision = self._reconcile(document, report)
        if decision["op"] == "NOOP":
            self._notify("page.noop", {"page": document.rel_path})
            return {"op": "NOOP", "page": None, **self._extra_result()}
        if decision["op"] == "UPDATE":
            document.rel_path = decision["target"]
        if decision["op"] == "SUPERSEDE":
            self._supersede(decision["target"], document.rel_path)
        result = self._writer.write(
            [document],
            log_kind=self.LOG_KIND if decision["op"] == "ADD" else "Update",
            log_message=draft.log_message or draft.title,
            commit_message=draft.commit_message or document.rel_path)
        self._after_write(document, report)
        return {"op": decision["op"], "page": document.rel_path,
                "commit": result["commit"], **self._extra_result()}

    # -------------------------------------------------------------- hooks
    @abstractmethod
    def _produce(self) -> DraftPage | None:
        """Gera o rascunho (extração+LLM, levantamento, sumário…)."""

    def _reconcile(self, document: OKFDocument, report) -> dict:
        return {"op": "ADD", "target": None}

    def _after_write(self, document: OKFDocument, report) -> None:
        pass

    def _extra_result(self) -> dict:
        return {}

    # -------------------------------------------------------- invariantes
    def _document(self, draft: DraftPage, body: str, report) -> OKFDocument:
        now = datetime.now(timezone.utc)
        meta = {"type": "concept", "title": draft.title,
                "timestamp": now, "valid_at": now,
                "privacy": "local_only",
                "entities": report.entities_frontmatter() or None,
                **draft.meta}
        if report.sensitive:                    # PII ⇒ LGPD topológica
            meta["privacy"] = "local_only"
            meta["sensitive_data"] = True
        return OKFDocument(
            rel_path=draft.rel_path, body=body,
            meta=OKFFrontMatter(**{k: v for k, v in meta.items()
                                   if v is not None}))

    def _supersede(self, old_path: str, new_path: str) -> None:
        """Invalidar, nunca apagar (zep): a antiga aponta para a nova."""
        old = self._writer.reader.load(old_path)
        meta = old.meta.model_dump(exclude_none=True)
        meta.update(superseded_by=new_path,
                    invalid_at=datetime.now(timezone.utc))
        self._writer.write(
            [OKFDocument(rel_path=old_path, body=old.body,
                         meta=OKFFrontMatter(**meta))],
            log_kind="Deprecation",
            log_message=f"supersedida por {new_path}",
            commit_message=f"supersede: {old_path}")
