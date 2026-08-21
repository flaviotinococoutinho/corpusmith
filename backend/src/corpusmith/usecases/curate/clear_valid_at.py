"""ClearLegacyValidAt — o resíduo do P-9, em lote e com preview (F4-PR3c).

O ADR-52 decisão 1 tirou o default de escrita: página de máquina só carrega
`valid_at` quando o conhecimento o fornece. Mas ele deixou explícito o que
NÃO fez — *"o legado de `valid_at` (~toda página de máquina existente) fica
INALTERADO até o ato em lote da F4-PR3: reescrever frontmatter em massa sem
preview seria exatamente o que o produto proíbe"*.

Este é aquele ato.

**Por que não precisa de contrato epistêmico.** A assinatura da corrupção é
igualdade, não limiar: página de máquina cujo `valid_at` é exatamente o
`timestamp` (`base._document` usava o MESMO objeto `now` nos dois campos).
`kernel/curation.valid_at_e_legado` é a regra, e ela é determinística — ao
contrário do `factual_conflict`, que carrega um número escolhido e por isso
declara garantia relativa. Aqui não há nada a calibrar.

**O ato REMOVE, não corrige.** Ausência de `valid_at` significa "nenhuma
alegação sobre quando o fato passou a valer", e o filtro `as_of` já tratava
a ausência como "passa". Recuperar o tempo de mundo REAL exigiria a fonte —
não é este ato, e prometer isso seria vender o que não se entrega.

**O preview é o instrumento de medida.** Não há corpus real neste
repositório para dimensionar o estrago, e não precisa haver: `execute(
dry_run=True)` roda só o `_plan()`, é puro, não escreve byte nenhum e não
move o HEAD. Rodá-lo no corpus do usuário responde exatamente quantas
páginas estão sujas e mostra o diff de cada uma.

**Teto declarado.** `~toda página de máquina existente` pode ser milhares.
Um preview com milhares de diffs torna a garantia central do eixo humano
NOMINAL — ninguém lê 3.000 diffs, e "preview obrigatório" vira teatro. O
lote tem limite, o preview diz quantas ficaram de fora, e repetir o ato
avança o resto.
"""
from __future__ import annotations
from .base import CurationAct, CurationPreview
from ...kernel.curation import sem_valid_at_legado, valid_at_e_legado
from ...okf.document import OKFDocument, OKFFrontMatter
from ...settings import Settings

#: Teto do lote. Não é limite técnico — é o ponto em que a revisão humana
#: do preview deixa de ser possível. Repetir o ato avança o resto.
LOTE_MAXIMO = 50


class ClearLegacyValidAt(CurationAct):
    ACT = "clear_legacy_valid_at"
    LOG_KIND = "Update"

    def __init__(self, settings: Settings, *, limit: int = LOTE_MAXIMO,
                 pages: list[str] | None = None, notify=None):
        super().__init__(settings, notify)
        self._limit = max(1, min(int(limit), LOTE_MAXIMO))
        self._only = set(pages or ())

    def _params(self) -> dict:
        return {"limit": self._limit, "pages": sorted(self._only) or None}

    # ------------------------------------------------------------ o alvo
    def _sujas(self) -> list[OKFDocument]:
        """Páginas com o carimbo colapsado, em ordem estável de caminho.

        Lê o BUNDLE, não o índice: a autoridade é o canônico (A-1), e um
        índice atrasado faria o lote pular página suja ou propor página
        que já foi limpa."""
        out = []
        for doc in self._writer.reader.iter_concepts():
            if self._only and doc.rel_path not in self._only:
                continue
            if valid_at_e_legado(doc.meta.model_dump(exclude_none=True)):
                out.append(doc)
        return sorted(out, key=lambda d: d.rel_path)

    def _documentos(self, sujas: list[OKFDocument]) -> list[OKFDocument]:
        return [OKFDocument(
            rel_path=d.rel_path, body=d.body,
            meta=OKFFrontMatter(**sem_valid_at_legado(
                d.meta.model_dump(exclude_none=True))))
            for d in sujas]

    # --------------------------------------------------------- esqueleto
    def _plan(self) -> CurationPreview:
        sujas = self._sujas()
        lote, resto = sujas[:self._limit], sujas[self._limit:]
        if not lote:
            return CurationPreview(
                act=self.ACT, pages=[],
                note="nenhuma página com `valid_at` colapsado — o resíduo "
                     "do P-9 está limpo neste bundle")
        partes = [
            f"{len(lote)} página(s) de máquina perdem o `valid_at` que o "
            "P-9 carimbou sozinho (ADR-52): o campo era igual ao "
            "`timestamp`, colapsando tempo de MUNDO em tempo de ESCRITA",
            "o ato REMOVE a alegação falsa, não recupera a verdadeira — "
            "ausência de `valid_at` significa `nenhuma alegação`, e "
            "recuperar quando o fato passou a valer exigiria a fonte",
            # a mudança de comportamento é o OBJETIVO do ato, e o usuário
            # não deveria descobri-la depois
            "efeito no `/ask`: hoje estas páginas são REBAIXADAS em "
            "qualquer consulta com `as_of` anterior à data de escrita — "
            "re-ranqueadas por um carimbo sem significado. Depois da "
            "limpeza voltam a competir normalmente",
            "nada é apagado do histórico: a remoção é um commit a mais, e "
            "`undo` reconstrói do commit pai",
        ]
        if resto:
            partes.append(
                f"TETO DO LOTE: {len(resto)} página(s) sujas ficam de fora "
                f"desta vez (limite {self._limit}). Repetir o ato avança o "
                "resto — o limite existe para que o preview continue "
                "legível, que é a garantia inteira do eixo humano")
        return self._preview_write(self._documentos(lote), self.ACT,
                                   note="; ".join(partes))

    def _apply(self, preview: CurationPreview) -> dict:
        sujas = [d for d in self._sujas() if d.rel_path in set(preview.pages)]
        return self._writer.write(
            self._documentos(sujas), log_kind=self.LOG_KIND,
            log_message=(f"P-9: `valid_at` colapsado removido de "
                         f"{len(sujas)} página(s) de máquina (ADR-52)"),
            commit_message=f"clear legacy valid_at: {len(sujas)} página(s)")
