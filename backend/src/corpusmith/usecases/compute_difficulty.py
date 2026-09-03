"""ComputeDifficulty — a projeção "o que é mais difícil de explicar" (V4).

**Camadas.** A REGRA (pesos, saturação, recusas) é pura e vive em
`kernel/difficulty.py`; aqui só se COLETA de cinco donos diferentes e se
persiste. Nenhuma decisão de domínio acontece neste arquivo — se um peso
aparecer aqui, o desenho quebrou.

**As cinco leituras, e de qual banco vem cada uma:**

| componente | fonte | camada |
|---|---|---|
| `falha_confiante` | `cognitive.db:retrieval_attempts` | prática humana |
| `conflito` | `check_corpus` (lint do corpus) | harness |
| `vocabulario_ambiguo` | idem (`policy.alias_conflict`) | harness/V2 |
| `pergunta_aberta` | bundle (`type: question` sem `answered_by`) | canônico |
| `lacuna_recorrente` | `runtime.db:ask_misses` × `index.db:page_entities` | F6 |

**Por que esta projeção NÃO é 100% re-derivável do canônico** — e por que
isso está certo aqui, ao contrário da V3: dois dos cinco sinais são
**uso** (prática e abstenção), e uso não mora no bundle por decisão de
produto (docs/30, memória por nível de acesso). A consequência é dita no
contrato: um clone novo calcula um índice mais pobre, com os componentes
determinísticos apenas — e o campo `medida` já distingue isso de "fácil".

**O salto de nível que a `lacuna_recorrente` faz** (docs/28 §2): um miss
é do nível da PERGUNTA; atribuí-lo a uma página exige que a página seja
*sobre* aquela entidade, o que se lê de `page_entities`. É aproximação
declarada, não precisão fingida — e o teto de saturação 3 limita o quanto
ela pode empurrar o índice.
"""
from __future__ import annotations
import json
from dataclasses import asdict

from .base import UseCase
from ..harness.local_policy import check_corpus
from ..kernel.difficulty import COMPONENTES, consolidar
from ..okf.bundle import BundleReader
from ..okf.links import is_internal, parse_links, resolve
from ..runtime.db import connect
from ..settings import Settings

#: Confiança declarada ANTES de conferir a partir da qual a falha conta
#: como sobreconfiança — o MESMO valor do `spaced-v1`
#: (`cognitive/policy.py:DEFAULT_POLICY["review"]["overconfidence_
#: threshold"]`), repetido aqui em vez de importado porque a memória não
#: importa `cognitive/` (asserção de arquitetura). Repetir constante
#: costuma ser dívida; aqui ela é PRESA por teste
#: (`test_limiar_de_sobreconfianca_e_o_mesmo_do_spaced_v1`) e declarada no
#: contrato, então divergir quebra a suíte em vez de virar duas definições
#: de "confiante" convivendo em silêncio.
_CONFIANCA = 0.7

#: Regras do lint de corpus que contam como sinal de dificuldade, e o
#: componente de cada uma. `policy.quotation_attribution` fica FORA de
#: propósito: citação mal atribuída é defeito de proveniência, não
#: dificuldade de explicar.
_REGRA_COMPONENTE = {
    "policy.contradiction_candidate": "conflito",
    "policy.factual_conflict": "conflito",
    "policy.alias_conflict": "vocabulario_ambiguo",
}


class ComputeDifficulty(UseCase):
    """Recomputa e persiste `page_difficulty`; devolve o ranking.

    `limit` corta só o RETORNO — a persistência é sempre completa, porque
    a projeção serve outros leitores (painel, fila)."""

    def __init__(self, settings: Settings, *, limit: int | None = None):
        self._settings = settings
        self._limit = max(1, int(limit)) if limit else None

    def execute(self) -> dict:
        kb = self._settings.path("knowledge")
        reader = BundleReader(kb / "bundle")
        docs = list(reader.iter_concepts())
        sinais: dict[str, dict[str, int]] = {
            d.rel_path: {c: 0 for c in COMPONENTES} for d in docs}

        self._do_lint(docs, reader, sinais)
        self._de_perguntas(docs, sinais)
        self._de_pratica(sinais)
        self._de_lacunas(sinais)

        ranking = consolidar(sinais)
        self._persistir(ranking)
        visiveis = ranking[:self._limit] if self._limit else ranking
        return {"pages": len(ranking),
                "measured": sum(1 for e in ranking if e.medida),
                "difficulty": [asdict(e) for e in visiveis]}

    # ------------------------------------------------------------ coleta
    def _do_lint(self, docs, reader, sinais) -> None:
        """Conflito e vocabulário ambíguo saem do MESMO lint — uma passada
        só, e a mesma fonte do painel Qualidade (nunca uma segunda
        implementação da mesma regra)."""
        for f in check_corpus(docs, reader):
            componente = _REGRA_COMPONENTE.get(f.rule)
            if componente is None:
                continue
            # o finding aponta a página ENTRINCHEIRADA, mas a dificuldade é
            # de todas as envolvidas: quem lê qualquer uma delas tromba no
            # mesmo desacordo
            alvos = set(f.meta.get("pages") or ()) | {f.path}
            for alvo in alvos:
                if alvo in sinais:
                    sinais[alvo][componente] += 1

    def _de_perguntas(self, docs, sinais) -> None:
        """Pergunta ABERTA (sem `answered_by`) que aponta para a página.

        A pergunta fechada não conta — foi respondida, e é justamente o
        gesto que tira a página da lista (a mesma leitura do
        `plan_attention`)."""
        for d in docs:
            meta = d.meta.model_dump(exclude_none=True)
            if meta.get("type") != "question" or meta.get("answered_by"):
                continue
            for link in parse_links(d.body):
                if not is_internal(link.target):
                    continue
                alvo = resolve(link.target, d.rel_path)
                if alvo in sinais:
                    sinais[alvo]["pergunta_aberta"] += 1

    def _de_pratica(self, sinais) -> None:
        """Falha de recuperação com confiança alta — o sinal humano.

        Banco cognitivo AUSENTE não é zero disfarçado: sem prática, o
        componente fica em 0 e o `medida` do kernel conta a história."""
        caminho = self._settings.app_support / "cognitive.db"
        if not caminho.is_file():
            return
        cog = connect(caminho)
        try:
            for row in cog.execute(
                    "SELECT item, COUNT(*) n FROM retrieval_attempts "
                    "WHERE result = 'failure' AND confidence_before >= ? "
                    "GROUP BY item", (_CONFIANCA,)):
                if row["item"] in sinais:
                    sinais[row["item"]]["falha_confiante"] += row["n"]
        finally:
            cog.close()

    def _de_lacunas(self, sinais) -> None:
        """Lacuna recorrente (F6): abstenção ABERTA sobre uma entidade que
        a página carrega. Miss fechado não conta — o buraco foi provado
        fechado por re-ask, e ressuscitá-lo aqui contradiria o F6."""
        rt = connect(self._settings.app_support / "runtime.db")
        try:
            entidades_por_miss = [json.loads(r["entities"] or "[]")
                                  for r in rt.execute(
                                      "SELECT entities FROM ask_misses "
                                      "WHERE closed_at IS NULL")]
        finally:
            rt.close()
        alvos = {e.lower() for grupo in entidades_por_miss for e in grupo}
        if not alvos:
            return
        idx = connect(self._settings.app_support / "index.db")
        try:
            for row in idx.execute(
                    "SELECT pe.page page, e.canonical canonical "
                    "FROM page_entities pe JOIN entities e "
                    "ON e.id = pe.entity_id"):
                if row["canonical"].lower() in alvos and row["page"] in sinais:
                    sinais[row["page"]]["lacuna_recorrente"] += 1
        finally:
            idx.close()

    # --------------------------------------------------------- persistir
    def _persistir(self, ranking) -> None:
        idx = connect(self._settings.app_support / "index.db")
        try:
            idx.execute("DELETE FROM page_difficulty")
            idx.executemany(
                "INSERT INTO page_difficulty(rel_path, score, measured, "
                "reason, components) VALUES (?,?,?,?,?)",
                [(e.rel_path, e.score, int(e.medida), e.motivo,
                  json.dumps(e.componentes, ensure_ascii=False))
                 for e in ranking])
            idx.commit()
        finally:
            idx.close()
