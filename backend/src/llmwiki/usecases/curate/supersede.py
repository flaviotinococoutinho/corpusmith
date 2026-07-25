"""SupersedePage — o ato humano que o Harness já mandava fazer.

`policy.contradiction_candidate` diz, literalmente, "resolva com
supersede/invalid_at ou funda as páginas" — e até aqui não havia como
fazer isso de dentro do produto: `_supersede` era método PROTEGIDO de
`MachinePageUseCase`, alcançável só quando a compilação decidia SUPERSEDE.

Invalidar-nunca-apagar: a página antiga continua no bundle e no Git, com
`superseded_by` apontando para a sucessora e `invalid_at` fechando sua
validade. TMS (Doyle 1979): quem dependia dela entra no preview para o
humano revisar — propagação de suspeita, nunca invalidação em cascata.
"""
from __future__ import annotations
from .base import CurationAct, CurationPreview
from ..mark_stale import dependents_of
from ...kernel.curation import superseded_meta
from ...okf.document import OKFDocument, OKFFrontMatter
from ...settings import Settings


class SupersedePage(CurationAct):
    ACT = "supersede"
    LOG_KIND = "Deprecation"

    def __init__(self, settings: Settings, page: str, successor: str,
                 *, reason: str = "", notify=None):
        super().__init__(settings, notify)
        self._page = page
        self._successor = successor
        self._reason = reason

    def _params(self) -> dict:
        return {"page": self._page, "successor": self._successor,
                "reason": self._reason}

    def _document(self) -> OKFDocument:
        antiga = self._writer.reader.load(self._page)
        meta = superseded_meta(antiga.meta.model_dump(exclude_none=True),
                               self._successor)
        return OKFDocument(rel_path=antiga.rel_path, body=antiga.body,
                           meta=OKFFrontMatter(**meta))

    def _plan(self) -> CurationPreview:
        if self._page == self._successor:
            raise ValueError("uma página não pode suceder a si mesma")
        # a sucessora precisa EXISTIR: apontar para o vazio criaria a
        # cadeia quebrada que nem o lint detecta hoje
        self._writer.reader.load(self._successor)
        return self._preview_write(
            [self._document()], self.ACT,
            dependents=dependents_of(self._settings, self._page),
            note=(f"{self._page} passa a apontar para {self._successor}; "
                  "nada é apagado — a antiga segue legível e no histórico"))

    def _apply(self, preview: CurationPreview) -> dict:
        return self._writer.write(
            [self._document()], log_kind=self.LOG_KIND,
            log_message=(f"supersedida por {self._successor}"
                         + (f": {self._reason}" if self._reason else "")),
            commit_message=f"supersede: {self._page} → {self._successor}")
