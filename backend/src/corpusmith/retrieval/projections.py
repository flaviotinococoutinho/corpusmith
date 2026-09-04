"""Leitura das projeções persistidas — o lado LEITOR do refresh (Q-1).

**O defeito que este módulo fecha, e ele era de desenho, não de código.**
Havia TRÊS caminhos para o mesmo número: `ComputeStability`/`ComputeDifficulty`
recomputavam e persistiam (CLI), `observatory.insights` lia o persistido, e
`ConceptSheet` recomputava ao montar. Três donos do mesmo valor produzem três
respostas possíveis para a mesma pergunta na mesma máquina — e a terceira,
por ser a da TELA, pagava o custo mais caro no momento mais sensível
(`git log` da história inteira + lint do bundle inteiro, por abertura de
ficha: o resíduo P-11 exatamente onde ele mais dói).

**A regra, agora com um lugar só onde ela mora:**

- **quem ESCREVE** é o comando/job de refresh (`corpusmith stability`,
  `corpusmith difficulty`, e o `MemoryFacade.stability/difficulty` que eles
  chamam) — ele recomputa e persiste;
- **quem LÊ** é este módulo, e ninguém mais toca nas tabelas de projeção. A
  ficha, o painel e as rotas do cockpit passam por aqui.

**`computed` não é `measured`, e confundir os dois é a mentira que este
módulo existe para impedir.** São três estados, não dois:

| estado | o que significa | como aparece |
|---|---|---|
| `computed=False` | a projeção NUNCA foi calculada nesta máquina | "ainda não calculado — rode `corpusmith …`" |
| `computed=True`, sem linha | calculada, e esta página não tem sinal | "nada observado" (≠ fácil, ≠ estável) |
| `computed=True`, com linha | há número, e ele vem com `means` e frescor | o valor + a ressalva do contrato |

Uma tela que empate os dois primeiros diz "nada observado" sobre uma base
que ninguém mediu — que é a autocertificação ao contrário: silêncio lido
como resultado.

O frescor vem do checkpoint `stability` (declarado em
`kernel/checkpoints.py:DERIVATIONS`), não de um carimbo novo. A dificuldade
NÃO tem derivação declarada de propósito (dois dos cinco sinais são de uso e
não movem o HEAD — carimbá-la prometeria um frescor que o uso não move), e
por isso ela reporta `freshness=None` em vez de fingir um veredito.
"""
from __future__ import annotations
import json

from ..normalize.gazetteer import base, sentido
from ..runtime.checkpoints import verify
from ..runtime.db import connect
from ..settings import Settings

#: O que "estável" quer dizer, viajando junto do número (nunca separado
#: dele: ressalva em página que ninguém abre não qualifica nada).
MEANS_STABILITY = ("quieto no eixo de EDIÇÃO — nunca 'correto' "
                   "nem 'aprovado'")
MEANS_DIFFICULTY = ("sem sinal NÃO é fácil de explicar: é nada "
                    "observado (ninguém praticou, nada conflita)")
#: O salto de nível da linha "sob qual lente", dito na própria linha
#: (docs/28 §2: atributo afirmado no nível errado é a patologia, declará-lo
#: é o preço de usá-lo mesmo assim).
MEANS_LENS = ("as entidades são MENÇÕES no texto; dizer que a página é "
              "'sobre' elas é um salto de nível (menção → página) que a "
              "contagem não prova")
MEANS_DIVERGENCE = ("desacordo DETECTADO entre páginas que citam o mesmo "
                    "identificador — não diz qual delas está certa")


def _tem_linhas(idx, tabela: str) -> bool:
    return idx.execute(f"SELECT 1 FROM {tabela} LIMIT 1").fetchone() is not None


def _freshness(settings: Settings, derivation: str) -> dict | None:
    for v in verify(settings):
        if v.derivation == derivation:
            return {"state": v.state, "reason": v.reason}
    return None


# ------------------------------------------------------------ estabilidade
def stability(settings: Settings, *, page: str | None = None,
              limit: int | None = None) -> dict:
    """`page_stability` como está no banco — jamais recomputada aqui.

    `page` devolve UMA linha (ou `None` com `computed` dizendo por quê);
    sem `page`, o ranking do mais quieto para o mais mexido."""
    idx = connect(settings.app_support / "index.db")
    try:
        computed = _tem_linhas(idx, "page_stability")
        if page is not None:
            linha = idx.execute(
                "SELECT rel_path, edits, first_commit_at, last_edit_at, "
                "lifecycle, computed_from FROM page_stability WHERE rel_path=?",
                (page,)).fetchone()
            corpo: dict = {"page": page,
                           "row": dict(linha) if linha else None}
        else:
            sql = ("SELECT rel_path, edits, first_commit_at, last_edit_at, "
                   "lifecycle, computed_from FROM page_stability "
                   "ORDER BY edits, rel_path")
            if limit:
                sql += f" LIMIT {max(1, int(limit))}"
            corpo = {"stability": [dict(r) for r in idx.execute(sql)],
                     "pages": idx.execute(
                         "SELECT COUNT(*) c FROM page_stability"
                     ).fetchone()["c"]}
        head = idx.execute(
            "SELECT computed_from FROM page_stability LIMIT 1").fetchone()
    finally:
        idx.close()
    return {**corpo,
            "computed": computed,
            "computed_from": head["computed_from"] if head else None,
            "freshness": _freshness(settings, "stability"),
            "means": MEANS_STABILITY,
            "refresh": "corpusmith stability"}


# -------------------------------------------------------------- dificuldade
def difficulty(settings: Settings, *, page: str | None = None,
               limit: int | None = None, measured_only: bool = False) -> dict:
    """`page_difficulty` como está no banco — jamais recomputada aqui."""
    idx = connect(settings.app_support / "index.db")
    try:
        computed = _tem_linhas(idx, "page_difficulty")
        if page is not None:
            linha = idx.execute(
                "SELECT rel_path, score, measured, reason, components "
                "FROM page_difficulty WHERE rel_path=?", (page,)).fetchone()
            corpo: dict = {"page": page,
                           "row": _linha_dificuldade(linha) if linha else None}
        else:
            sql = ("SELECT rel_path, score, measured, reason, components "
                   "FROM page_difficulty")
            if measured_only:
                sql += " WHERE measured = 1"
            sql += " ORDER BY score DESC, rel_path"
            if limit:
                sql += f" LIMIT {max(1, int(limit))}"
            corpo = {"difficulty": [_linha_dificuldade(r)
                                    for r in idx.execute(sql)],
                     "measured": idx.execute(
                         "SELECT COUNT(*) c FROM page_difficulty "
                         "WHERE measured = 1").fetchone()["c"]}
    finally:
        idx.close()
    # sem derivação declarada: `freshness` AUSENTE é honesto, um veredito
    # inventado não seria (o uso move o número sem mover o HEAD)
    return {**corpo, "computed": computed, "freshness": None,
            "means": MEANS_DIFFICULTY, "refresh": "corpusmith difficulty"}


def _linha_dificuldade(row) -> dict:
    d = dict(row)
    d["measured"] = bool(d["measured"])
    d["components"] = json.loads(d.get("components") or "{}")
    return d


# --------------------------------------------------------------- divergência
def divergence(settings: Settings, page: str) -> dict:
    """"Onde diverge": os grupos de desacordo que incluem esta página.

    `computed` vem de `page_difficulty` (a MESMA passada de lint que escreve
    as duas) — a tabela de divergência vazia é o estado NORMAL de um corpus
    sem conflito, e lê-la como "nunca calculado" acusaria falso em toda base
    saudável."""
    idx = connect(settings.app_support / "index.db")
    try:
        computed = _tem_linhas(idx, "page_difficulty")
        linhas = [dict(r) for r in idx.execute(
            "SELECT rule, identifier, with_pages, message FROM page_divergence "
            "WHERE rel_path = ? ORDER BY rule, identifier", (page,))]
    finally:
        idx.close()
    for linha in linhas:
        linha["with_pages"] = [p for p in json.loads(linha["with_pages"] or "[]")
                               if p != page]
    return {"page": page, "computed": computed, "conflicts": linhas,
            "means": MEANS_DIVERGENCE, "refresh": "corpusmith difficulty"}


# --------------------------------------------------------------------- lente
def lens(settings: Settings, page: str, *, limit: int = 12) -> dict:
    """"Sob qual lente": as identidades que a página menciona (V2).

    O sentido curado (`Entropia (física)`) é o que responde "sob qual
    lente" — sem ele, `base == canonical` e a lente é o próprio termo. Não
    há recomputação: `page_entities` é escrita pelo `rebuild_index`, e um
    índice ausente devolve `computed=False` em vez de lista vazia.

    **A testemunha de `computed` é `page_index_state`, não
    `page_entities`** — medido numa execução real sobre bundle sintético:
    um índice que RODOU e não reconheceu identidade nenhuma tem
    `page_entities` vazia, e usá-la como testemunha dizia "ainda não
    calculado" sobre um índice fresco. É o mesmo erro que este módulo
    existe para impedir, cometido do outro lado: resultado lido como
    silêncio."""
    idx = connect(settings.app_support / "index.db")
    try:
        computed = _tem_linhas(idx, "page_index_state")
        linhas = [dict(r) for r in idx.execute(
            "SELECT e.canonical canonical, e.authority authority, "
            "e.kind kind, SUM(pe.n) mentions, "
            "MAX(pe.confidence = 'ambiguous') ambiguous "
            "FROM page_entities pe JOIN entities e ON e.id = pe.entity_id "
            "WHERE pe.page = ? GROUP BY e.canonical, e.authority, e.kind "
            "ORDER BY mentions DESC, e.canonical", (page,))]
    finally:
        idx.close()
    entidades = [{"canonical": r["canonical"],
                  "base": base(r["canonical"]),
                  "sense": sentido(r["canonical"]),
                  "authority": r["authority"],
                  "kind": r["kind"],
                  # V2/`alias_conflict`: alias disputado é lido como
                  # AMBÍGUO — mostrá-lo como lente firme seria vender
                  # desambiguação que não houve
                  "ambiguous": bool(r["ambiguous"]),
                  "mentions": int(r["mentions"] or 0)}
                 for r in linhas[:limit]]
    return {"page": page, "computed": computed, "entities": entidades,
            "total": len(linhas),
            "qualified": sum(1 for e in entidades if e["sense"]),
            "level": "mention",
            "means": MEANS_LENS,
            "refresh": "corpusmith okf index"}
