"""MergePages — fundir duas versões da mesma verdade (F1-PR5, ADR-41.5).

Último ato da Fase 1, e o que o próprio Harness pede por escrito: o finding
`policy.contradiction_candidate` diz "resolva com supersede/invalid_at **ou
funda as páginas**". `supersede` (F1-PR1) cobre a primeira metade desde o
começo da fase; esta é a segunda — e é a resolução que não pede a ninguém
para abandonar texto.

Um ato, duas escritas, um commit:

- **vencedora** (`into`): frontmatter recebe a união declarada
  (`kernel/curation.py:merge_meta`) e o corpo recebe o texto da perdedora
  INTEGRAL, numa região sentinelada (`okf/absorbed.py`);
- **perdedora** (`page`): corpo intocado, frontmatter ganha
  `superseded_by`/`invalid_at` (`superseded_meta` — o MESMO do supersede).

Nenhum byte se perde: a perdedora continua legível no caminho dela (o HEAD
do Git tem as duas) e seu texto passa a ser legível também de dentro da
vencedora — que é o que "as duas versões param de conviver" precisa
significar para quem lê.

**A decisão D-D do `docs/15`, resolvida por medição.** O plano dava duas
saídas ("preview lento por design" ou "antecipar a memoização da F7"),
partindo de que ver a contradição custaria os 16-40 s do P-11. Medido, o
custo é de `lint_bundle` (que roda TODOS os checks), não de `check_corpus`:
este sai por ~1,2 ms/doc + ~45 ms de gazetteer. E principalmente: a
pergunta que o preview precisa responder é sobre AS DUAS PÁGINAS do ato,
não sobre o bundle. Então o preview roda `check_corpus` nos dois documentos
ANTES (o finding que o ato resolve) e nos dois DEPOIS (a prova de que
sumiu), e consulta `page_entities` — projeção JÁ construída, com índice por
entidade — para saber se o identificador aparece em MAIS alguma página.
Terceira saída: sem varredura e sem memoização.

Essa terceira página importa por uma razão que o preview declara em vez de
esconder: `check_corpus` marca o grupo inteiro como resolvido quando UMA
sucessão aparece nele. Fundir A em B silencia o finding também para o par
(B, C) — o alerta desaparece sem que aquela convivência tenha sido tratada.
"""
from __future__ import annotations
from .base import CurationAct, CurationPreview
from ..mark_stale import dependents_of
from ...harness.local_policy import CONTRADICTION_IDS, check_corpus
from ...kernel.curation import (merge_meta, mergeable_source_meta,
                                superseded_meta)
from ...okf.absorbed import with_absorbed
from ...okf.document import OKFDocument, OKFFrontMatter
from ...runtime.db import connect
from ...settings import Settings


class MergePages(CurationAct):
    ACT = "merge"
    LOG_KIND = "Update"

    def __init__(self, settings: Settings, page: str, into: str,
                 *, reason: str = "", notify=None):
        super().__init__(settings, notify)
        self._page = page              # a absorvida (perdedora)
        self._into = into              # a que sobrevive (vencedora)
        self._reason = reason

    def _params(self) -> dict:
        return {"page": self._page, "into": self._into,
                "reason": self._reason}

    # ------------------------------------------------------------ documentos
    def _documentos(self) -> list[OKFDocument]:
        perdedora = self._writer.reader.load(self._page)
        vencedora = self._writer.reader.load(self._into)
        meta_p = perdedora.meta.model_dump(exclude_none=True)
        nova = merge_meta(vencedora.meta.model_dump(exclude_none=True),
                          mergeable_source_meta(meta_p))
        absorvida = OKFDocument(
            rel_path=vencedora.rel_path,
            body=with_absorbed(vencedora.body, self._page,
                               perdedora.meta.title or self._page,
                               perdedora.body),
            meta=OKFFrontMatter(**nova))
        aposentada = OKFDocument(
            rel_path=perdedora.rel_path, body=perdedora.body,
            meta=OKFFrontMatter(**superseded_meta(meta_p, self._into)))
        return [absorvida, aposentada]

    # ------------------------------------------------- a contradição resolvida
    def _identificadores_compartilhados(self, docs) -> list[dict]:
        """Findings de contradição ENTRE os documentos dados — o detector
        existente, sem heurística nova (seria RFC, AGENTS.md §8)."""
        return [{"identifier": f.meta.get("identifier"),
                 "pages": f.meta.get("pages", []), "message": f.message}
                for f in check_corpus(docs, self._writer.reader)]

    def _outras_paginas_com(self, identificadores: list[str]) -> list[str]:
        """Páginas fora do par que citam os mesmos identificadores fortes.

        Vem da PROJEÇÃO (`page_entities`, índice por entidade), não de uma
        varredura: é a informação que `rebuild_index` já mantém. Como é
        projeção, vale o quanto valer o último rebuild — e todo `_apply`
        roda um."""
        if not identificadores:
            return []
        idx = connect(self._settings.app_support / "index.db")
        try:
            marcas = ",".join("?" * len(identificadores))
            tipos = ",".join("?" * len(CONTRADICTION_IDS))
            rows = idx.execute(
                "SELECT DISTINCT pe.page FROM page_entities pe "
                "JOIN entities e ON e.id = pe.entity_id "
                f"WHERE e.canonical IN ({marcas}) AND e.kind IN ({tipos})",
                (*identificadores, *CONTRADICTION_IDS)).fetchall()
        except Exception:
            return []            # índice ausente/antigo não bloqueia o ato
        finally:
            idx.close()
        return sorted({r["page"] for r in rows} - {self._page, self._into})

    def _nota(self, docs: list[OKFDocument]) -> str:
        antes = self._identificadores_compartilhados(
            [self._writer.reader.load(self._page),
             self._writer.reader.load(self._into)])
        partes = [f"o texto de {self._page} entra INTEGRAL numa região "
                  f"declarada de {self._into} (nenhuma prosa é reescrita) e "
                  f"{self._page} passa a apontar para {self._into} — nada é "
                  "apagado, as duas seguem no histórico"]
        if antes:
            depois = self._identificadores_compartilhados(docs)
            ids = ", ".join(str(f["identifier"]) for f in antes)
            if depois:
                partes.append(
                    f"ATENÇÃO: o identificador compartilhado ({ids}) CONTINUA "
                    "em conflito depois da fusão — verifique o preview")
            else:
                partes.append(f"esta fusão RESOLVE a contradição candidata do "
                              f"identificador {ids}")
            terceiras = self._outras_paginas_com(
                [f["identifier"] for f in antes if f["identifier"]])
            if terceiras:
                partes.append(
                    "mas o mesmo identificador também aparece em "
                    + ", ".join(terceiras)
                    + " — essa convivência NÃO é tratada aqui e SEGUE na "
                      "fila depois desta fusão (F3-PR2: a sucessão resolve "
                      "só o bloco que ela liga, não o grupo inteiro)")
        return "; ".join(partes)

    # ------------------------------------------------------------- esqueleto
    def _plan(self) -> CurationPreview:
        if self._page == self._into:
            raise ValueError("uma página não pode ser fundida em si mesma")
        perdedora = self._writer.reader.load(self._page)
        self._writer.reader.load(self._into)          # a vencedora tem de existir
        ja = perdedora.meta.model_dump(exclude_none=True).get("superseded_by")
        if ja:
            raise ValueError(
                f"{self._page} já foi supersedida por {ja} — fundir agora "
                "criaria duas sucessoras para a mesma página")
        docs = self._documentos()
        dependentes = sorted(set(dependents_of(self._settings, self._page))
                             | set(dependents_of(self._settings, self._into)))
        return self._preview_write(docs, self.ACT, dependents=dependentes,
                                   note=self._nota(docs))

    def _apply(self, preview: CurationPreview) -> dict:
        return self._writer.write(
            self._documentos(), log_kind=self.LOG_KIND,
            log_message=(f"fundida {self._page} em {self._into}"
                         + (f" — {self._reason}" if self._reason else "")),
            commit_message=f"merge: {self._page} → {self._into}")
