"""EditPage — a primeira escrita HUMANA de corpo (F1-PR3, ADR-41.4).

Fecha a falha da "1ª correção" da tabela de viabilidade do `docs/14`: o
painel Wiki era somente-leitura com um botão ("marcar stale"), não existia
use case, endpoint nem CLI de edição, e a correção acontecia FORA do
produto — onde o doctor nem detecta a divergência, porque INV-002 compara
`bundle_head` com o HEAD do Git e edição não commitada não move o HEAD.

É também o ato que resolve `low_yield`: uma página que "deu beco" não
expirou no mundo (não é `invalidate`) nem tem sucessora (não é
`supersede`) — o que ela precisa é ter o corpo corrigido. Por isso
`acts_for` deixou `low_yield` sem ato até agora, e é este PR que muda isso.
(O-6: o nome antigo era `contested`; a partir do ADR-54 essa palavra é do
eixo `resolution_status` e significa divergência factual, não beco.)

**A prosa NÃO passa pelo sanduíche.** `normalize_machine_body` reescreve
grafia canônica e é o eixo de MÁQUINA (v0.8 §1.2 — o Harness aplica só a
política de página humana). Um ato humano que a chamasse reescreveria o
texto do autor. Há teste por AST garantindo que nada em `curate/` a
importa.

**O que este ato NÃO faz**, por decisão: não muda o `rel_path` (a
identidade OKF É o caminho — renomear é outro ato, e o SPEC fixa isso) e
não REMOVE chave de frontmatter (removida disparia `policy.metadata_shrink`
no gate; apagar declaração é gesto diferente de corrigir).
"""
from __future__ import annotations
from .base import CurationAct, CurationPreview
from ..mark_stale import dependents_of
from ...okf.document import OKFDocument, OKFFrontMatter
from ...settings import Settings


class EditPage(CurationAct):
    ACT = "edit"
    LOG_KIND = "Update"

    def __init__(self, settings: Settings, page: str,
                 body: str | None = None,
                 meta_patch: dict | None = None,
                 *, reason: str = "", notify=None):
        super().__init__(settings, notify)
        self._page = page
        self._body = body
        self._patch = dict(meta_patch or {})
        self._reason = reason

    def _params(self) -> dict:
        return {"page": self._page, "reason": self._reason,
                "body_len": len(self._body or ""),
                "meta_keys": sorted(self._patch)}

    def _documento(self) -> OKFDocument:
        atual = self._writer.reader.load(self._page)
        meta = atual.meta.model_dump(exclude_none=True)
        # patch MESCLA; remover chave é gesto diferente (metadata_shrink)
        vazias = [k for k, v in self._patch.items() if v in (None, "")]
        if vazias:
            raise ValueError(
                f"este ato não REMOVE campo de frontmatter ({', '.join(vazias)})"
                " — apagar declaração é gesto diferente de corrigir, e o gate "
                "acusaria policy.metadata_shrink")
        meta.update(self._patch)
        return OKFDocument(
            rel_path=atual.rel_path,               # identidade = caminho
            body=self._body if self._body is not None else atual.body,
            meta=OKFFrontMatter(**meta))

    def _plan(self) -> CurationPreview:
        if self._body is None and not self._patch:
            raise ValueError("nada a editar: informe corpo e/ou meta_patch")
        if "rel_path" in self._patch or "path" in self._patch:
            raise ValueError(
                "a identidade OKF é o caminho da página — renomear não é "
                "edição; use suceder (o histórico preserva as duas)")
        documento = self._documento()
        partes = []
        if self._body is not None:
            partes.append("corpo")
        if self._patch:
            partes.append("frontmatter (" + ", ".join(sorted(self._patch)) + ")")
        return self._preview_write(
            [documento], self.ACT,
            dependents=dependents_of(self._settings, self._page),
            note=(f"edita {' e '.join(partes)} de {self._page}; a prosa vai "
                  "COMO ESCRITA — nenhuma normalização de grafia é aplicada "
                  "a texto humano"))

    def _apply(self, preview: CurationPreview) -> dict:
        return self._writer.write(
            [self._documento()], log_kind=self.LOG_KIND,
            log_message=(f"editada: {self._page}"
                         + (f" — {self._reason}" if self._reason else "")),
            commit_message=f"edit: {self._page}")
