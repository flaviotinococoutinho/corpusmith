"""InvalidatePage — declarar que um fato DEIXOU DE VALER, sem sucessora.

Diferente de `stale_as_of` (tempo de CÓDIGO: "isto talvez precise de
revisão") e de `supersede` (existe uma versão nova): aqui o curador afirma
que a proposição expirou no MUNDO, em uma data. É o único gesto que
escreve `invalid_at` por decisão humana — e é o que faz a partição
temporal do retrieval (`streams.py`, que já sabe filtrar por `as_of`)
finalmente ter dado real para filtrar.

A página continua legível: invalidar não é apagar nem esconder — o /ask
segue podendo citá-la para uma pergunta ancorada no passado.
"""
from __future__ import annotations
from datetime import datetime, timezone
from .base import CurationAct, CurationPreview
from ..mark_stale import dependents_of
from ...kernel.curation import invalidated_meta
from ...okf.document import OKFDocument, OKFFrontMatter
from ...settings import Settings


class InvalidatePage(CurationAct):
    ACT = "invalidate"
    LOG_KIND = "Deprecation"

    def __init__(self, settings: Settings, page: str,
                 invalid_at: str | datetime | None = None,
                 *, reason: str = "", notify=None):
        super().__init__(settings, notify)
        self._page = page
        self._when = self._parse(invalid_at)
        self._reason = reason

    @staticmethod
    def _parse(value: str | datetime | None) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(
                tzinfo=timezone.utc)
        if not value:
            return datetime.now(timezone.utc)
        texto = str(value).replace("Z", "+00:00")
        quando = datetime.fromisoformat(texto)
        return quando if quando.tzinfo else quando.replace(
            tzinfo=timezone.utc)

    def _params(self) -> dict:
        return {"page": self._page, "invalid_at": self._when,
                "reason": self._reason}

    def _document(self) -> OKFDocument:
        atual = self._writer.reader.load(self._page)
        meta = invalidated_meta(atual.meta.model_dump(exclude_none=True),
                                self._when, self._reason or None)
        return OKFDocument(rel_path=atual.rel_path, body=atual.body,
                           meta=OKFFrontMatter(**meta))

    def _plan(self) -> CurationPreview:
        return self._preview_write(
            [self._document()], self.ACT,
            dependents=dependents_of(self._settings, self._page),
            note=(f"{self._page} deixa de valer em "
                  f"{self._when.date().isoformat()}; segue legível e "
                  "citável para perguntas ancoradas antes dessa data"))

    def _apply(self, preview: CurationPreview) -> dict:
        return self._writer.write(
            [self._document()], log_kind=self.LOG_KIND,
            log_message=(f"invalidada em {self._when.date().isoformat()}"
                         + (f": {self._reason}" if self._reason else "")),
            commit_message=f"invalidate: {self._page}")
