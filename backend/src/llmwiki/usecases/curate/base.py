"""CurationAct — Template Method do eixo HUMANO (F1-PR1, ADR-41).

Irmão de `MachinePageUseCase`, e deliberadamente NÃO subclasse dele: o
esqueleto de máquina passa o corpo pelo sanduíche de normalização
(`normalize_machine_body`), o que é proibido para prosa humana (v0.8 §1.2
— o Harness aplica só a política de página humana). O que os dois eixos
compartilham são as TRANSFORMAÇÕES puras (`kernel/curation.py`) e o gate
único de escrita (`okf/writer.py`), não a herança.

Esqueleto IMUTÁVEL, por isso `execute` é fechado (asserção de arquitetura,
irmã do INV-ARCH-006):

    _plan()  → preview PURO: diff por página, findings PREVISTOS pelo
               Harness em mode='write' SEM escrever, páginas tocadas,
               dependentes TMS. Zero bytes no bundle, HEAD imóvel.
    _apply() → UMA chamada ao BundleWriter (log_kind explícito) →
               registro em `curation_acts` com o sha do commit →
               rebuild_index incremental da projeção.

`execute(dry_run=True)` roda só `_plan()`. Sem `dry_run` roda os dois — e
recusa quando o preview já prevê erro, para o ato não morrer no meio do
rito. `curation_acts` é ÍNDICE de atos, não verdade paralela: a autoridade
do que aconteceu continua sendo o Git + `log.md`, e por isso cada linha
guarda o `commit`.
"""
from __future__ import annotations
import json
import threading
from abc import abstractmethod
from dataclasses import dataclass, field
from ..base import UseCase
from ...harness.runner import HarnessRejection, HarnessRunner
from ...kernel.curation import unified_diff
from ...okf.document import OKFDocument
from ...okf.writer import BundleWriter
from ...retrieval.fts import rebuild_index
from ...runtime.db import connect
from ...settings import Settings


@dataclass
class CurationPreview:
    """O que o ato VAI fazer, calculado sem efeito nenhum."""
    act: str
    pages: list[str]
    diffs: dict[str, str] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def blocked(self) -> bool:
        """Preview que já prevê erro do Harness: aplicar levantaria
        HarnessRejection dentro do rito — melhor recusar antes."""
        return any(f["severity"] == "error" for f in self.findings)

    def to_dict(self) -> dict:
        return {"act": self.act, "pages": self.pages, "diffs": self.diffs,
                "findings": self.findings, "dependents": self.dependents,
                "note": self.note, "blocked": self.blocked}


class CurationAct(UseCase):
    """Um ato humano sobre o canônico. Subclasses preenchem só os hooks."""

    ACT = "act"
    LOG_KIND = "Update"
    # D-H (docs/15 §5): o flock do writer serializa só a ESCRITA — o plano
    # podia ser computado sobre estado que outro ato mudou entre o plan e o
    # apply, e o rebuild corria fora de qualquer lock. Este mutex fecha o
    # rito inteiro (plan→apply→record→rebuild) no processo do daemon, onde
    # todos os atos HTTP rodam. Resíduo declarado: CLI × daemon são
    # processos distintos — lá o flock segue garantindo a escrita, mas um
    # plano pode envelhecer entre processos (mesma janela de antes, agora
    # dita em voz alta).
    _rito = threading.Lock()

    def __init__(self, settings: Settings, notify=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)
        self._writer = BundleWriter(settings.path("knowledge"))

    # ------------------------------------------------- esqueleto IMUTÁVEL
    def execute(self, dry_run: bool = False) -> dict:
        if dry_run:
            # CQS: o preview é puro e não disputa o rito com ninguém
            return {"dry_run": True, "applied": False,
                    "preview": self._plan().to_dict()}
        with self._rito:
            return self._executar_serializado()

    def _executar_serializado(self) -> dict:
        preview = self._plan()
        if preview.blocked:
            # o rito não começa se o preview já prevê rejeição: assim o
            # 422 sai do MESMO cálculo que o usuário viu no dry-run
            raise HarnessRejection(self._findings_for(preview))
        result = self._apply(preview)
        act_id = self._record(preview, result.get("commit"))
        rebuild_index(self._settings)
        self._notify("curation.applied",
                     {"act": self.ACT, "id": act_id,
                      "pages": preview.pages,
                      "commit": result.get("commit")})
        return {"dry_run": False, "applied": True, "id": act_id,
                "preview": preview.to_dict(), **result}

    # -------------------------------------------------------------- hooks
    @abstractmethod
    def _plan(self) -> CurationPreview:
        """PURO: nenhum byte escrito, HEAD imóvel, nada registrado."""

    @abstractmethod
    def _apply(self, preview: CurationPreview) -> dict:
        """UMA chamada ao writer. Devolve pelo menos {"commit": sha}."""

    def _params(self) -> dict:
        """Parâmetros do ato, para a trilha (e para o undo reconstruir)."""
        return {}

    # ---------------------------------------------------------- utilidades
    def _preview_write(self, docs: list[OKFDocument], act: str, *,
                       dependents: list[str] | None = None,
                       note: str = "") -> CurationPreview:
        """Diff + findings PREVISTOS sem tocar o disco: roda o MESMO
        `HarnessRunner.run(mode='write')` que o writer roda, só que
        descartando o resultado em vez de escrever."""
        runner = HarnessRunner(self._writer.reader, self._writer.git)
        findings = runner.run(docs, mode="write")
        diffs, reformatadas = {}, []
        bundle = self._writer.bundle
        for doc in docs:
            # bytes CRUS do disco como "antes" (F1-PR3). Usar
            # `reader.load().dumps()` SUBDECLARAVA: a escrita reordena as
            # chaves do frontmatter, injeta `tags: []` e normaliza o fim do
            # arquivo, então uma página editada à mão mudava MAIS do que o
            # preview mostrava. Medido: ordem própria de chave + ausência de
            # `tags` ⇒ `dumps()` != bytes no disco.
            caminho = bundle / doc.rel_path
            antes = caminho.read_text() if caminho.is_file() else ""
            depois = doc.dumps()
            diffs[doc.rel_path] = unified_diff(antes, depois, doc.rel_path)
            if antes:
                try:
                    canonico = self._writer.reader.load(doc.rel_path).dumps()
                except Exception:
                    canonico = antes
                if canonico != antes:
                    reformatadas.append(doc.rel_path)
        if reformatadas:
            note = (note + ("; " if note else "")
                    + "esta escrita também NORMALIZA o formato de "
                    + ", ".join(reformatadas)
                    + " (ordem das chaves do frontmatter, campos com default, "
                      "fim do arquivo) — o diff mostra isso junto")
        return CurationPreview(act=act, pages=[d.rel_path for d in docs],
                               diffs=diffs,
                               findings=[f.__dict__ for f in findings],
                               dependents=dependents or [], note=note)

    def _findings_for(self, preview: CurationPreview):
        from ...harness.findings import Finding, Findings
        return Findings(Finding(**f) for f in preview.findings)

    def _record(self, preview: CurationPreview, commit: str | None) -> int:
        """UMA transação: a trilha nunca fica pela metade. Atos que
        precisam gravar mais (o undo liga `undoes`/`undone_by`) usam o
        hook `_record_extra`, que roda na MESMA conexão antes do commit —
        senão haveria uma janela em que a trilha afirma um ato sem os
        vínculos que o explicam."""
        rt = connect(self._settings.app_support / "runtime.db")
        try:
            cur = rt.execute(
                "INSERT INTO curation_acts(act, params, commit_sha, pages) "
                "VALUES (?,?,?,?)",
                (self.ACT, json.dumps(self._params(), default=str), commit,
                 json.dumps(preview.pages)))
            act_id = cur.lastrowid
            self._record_extra(rt, act_id)
            rt.commit()
        finally:
            rt.close()
        return act_id

    def _record_extra(self, conn, act_id: int) -> None:
        """Hook: gravações adicionais na MESMA transação da trilha."""
