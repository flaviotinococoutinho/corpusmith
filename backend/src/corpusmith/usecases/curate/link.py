"""LinkPages / UnlinkPages — a relação escrita no CANÔNICO (F1-PR4).

É o ato de maior densidade valor/custo da fila: `bridge_items` já entrega
`action.type='link'` com src/dst, e até aqui esse item do topo levava ao
Grafo, que não tem afordância de aresta. Agora ele tem destino.

Por que no corpo e não no frontmatter: `retrieval/fts.py` só faz
`parse_links(d.body)` — relação em frontmatter não viraria aresta, e a
promessa do plano ("o reparo sobrevive ao rebuild") não aconteceria.

Por que um bloco sentinelado: o unlink precisa distinguir o link que o ATO
pôs do link que o HUMANO escreveu na prosa. A proveniência é da REGIÃO, não
do link — o ato só mexe entre as sentinelas, e por construção nunca
reescreve prosa. Quando existe link na prosa para o mesmo alvo, o unlink
DECLARA no preview que a aresta sobrevive: melhor um contrato explícito que
um "não funcionou" silencioso.
"""
from __future__ import annotations
from .base import CurationAct, CurationPreview
from ..mark_stale import dependents_of
from ...okf.document import OKFDocument, OKFFrontMatter
from ...okf.relations import prose_links_to, with_link, without_link
from ...settings import Settings


class _AtoDeRelacao(CurationAct):
    """Parte comum: valida o par e monta o documento com o corpo novo."""

    def __init__(self, settings: Settings, src: str, dst: str, *,
                 rel: str | None = None, notify=None):
        super().__init__(settings, notify)
        self._src = src
        self._dst = dst
        self._rel = rel

    def _params(self) -> dict:
        return {"src": self._src, "dst": self._dst, "rel": self._rel}

    def _origem(self) -> OKFDocument:
        if self._src == self._dst:
            raise ValueError("uma página não se relaciona consigo mesma")
        return self._writer.reader.load(self._src)

    def _documento(self, corpo: str) -> OKFDocument:
        origem = self._writer.reader.load(self._src)
        return OKFDocument(
            rel_path=origem.rel_path, body=corpo,
            meta=OKFFrontMatter(**origem.meta.model_dump(exclude_none=True)))


class LinkPages(_AtoDeRelacao):
    ACT = "link"
    LOG_KIND = "Update"

    def _corpo(self) -> str:
        origem = self._origem()
        alvo = self._writer.reader.load(self._dst)   # tem de existir
        titulo = alvo.meta.title or self._dst
        return with_link(origem.body, self._src, self._dst, titulo, self._rel)

    def _plan(self) -> CurationPreview:
        return self._preview_write(
            [self._documento(self._corpo())], self.ACT,
            dependents=dependents_of(self._settings, self._src),
            note=(f"acrescenta {self._dst} ao bloco de relações de "
                  f"{self._src}; a prosa não é tocada e a aresta passa a "
                  "existir no grafo após a reindexação"))

    def _apply(self, preview: CurationPreview) -> dict:
        return self._writer.write(
            [self._documento(self._corpo())], log_kind=self.LOG_KIND,
            log_message=f"relação {self._src} → {self._dst}",
            commit_message=f"link: {self._src} → {self._dst}")


class UnlinkPages(_AtoDeRelacao):
    ACT = "unlink"
    LOG_KIND = "Update"

    def _corpo(self) -> str:
        origem = self._origem()
        return without_link(origem.body, self._src, self._dst)

    def _plan(self) -> CurationPreview:
        origem = self._origem()
        corpo = self._corpo()
        residuo = prose_links_to(origem.body, self._src, self._dst)
        nota = (f"remove {self._dst} do bloco de relações de {self._src}; "
                "nada fora do bloco é tocado")
        if residuo:
            nota += (f"; ATENÇÃO: a prosa ainda cita {self._dst} "
                     f"({len(residuo)} link(s)) — a ARESTA CONTINUA no grafo. "
                     "Remover isso seria reescrever prosa do autor, e este "
                     "ato não faz isso.")
        return self._preview_write(
            [self._documento(corpo)], self.ACT,
            dependents=dependents_of(self._settings, self._src), note=nota)

    def _apply(self, preview: CurationPreview) -> dict:
        return self._writer.write(
            [self._documento(self._corpo())], log_kind=self.LOG_KIND,
            log_message=f"relação removida {self._src} → {self._dst}",
            commit_message=f"unlink: {self._src} → {self._dst}")
