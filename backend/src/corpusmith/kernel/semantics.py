"""Vocabulário das relações SEMÂNTICAS entre páginas — PURO (RFC-006, V5).

**O que este módulo NÃO é**, e o nome importa porque o repositório já
pagou por ambiguidade de nome: aqui não se fala de *forma* de link
(`okf/relations.py` cuida do bloco e `okf/links.py` da sintaxe), nem de
*ponte topológica* (`graph_bridges`: dois blocos do grafo que quase não
se conectam — estrutura, não significado). Este módulo responde a uma
pergunta só: **que tipo de relação um humano declarou entre duas
páginas?**

**Por que fechado.** O `rel:` já existia no canônico e era ABERTO —
`rel:serve_pra` entrava e ficava lá para sempre, sem ninguém saber
reinterpretá-lo depois. É a mesma patologia que o `ontology.toml`
existe para impedir: valor de vocabulário sem fronteira declarada. Cada
verbete abaixo carrega a PERGUNTA que responde e o que ele **não**
significa, porque relação vizinha é onde o sentido escorrega.

**Por que os nomes são em inglês**, contra o resto do texto deste
arquivo: valor que entra no CANÔNICO é inglês neste produto
(`extracted`, `human_approved`, `low_yield`, `ADD`/`SUPERSEDE`), e
`refines` já existia como exemplo vivo em `okf/links.py` e na suíte
desde a v1.8.2. Inventar `refina` teria criado um segundo nome para a
mesma coisa e quebrado bundles que já usam o primeiro — a suíte pegou
isso na primeira execução.

**Estrito na escrita, tolerante na leitura.** O ato de curadoria recusa
relação fora da tabela (o canônico é para sempre); a projeção converte
desconhecido em `None` — "não tipada" — porque um bundle antigo, ou um
link escrito à mão na prosa, não pode derrubar um rebuild.

**O nível, dito em voz alta** (docs/28 §2): a aresta liga PÁGINAS. Dizer
"este conceito se aplica a esta página" afirma que a página inteira é o
caso — quando ela carrega várias afirmações, a declaração é mais grossa
que a realidade. Essa é a granularidade que a RFC-004 §6 quer ver MEDIDA
antes de reabrir o nível da afirmação, e `usecases/practical_cases.py` é
quem mede.
"""
from __future__ import annotations

#: `direcao` diz de que lado do abstrato a ORIGEM está. Sem isso,
#: "A applies_to B" e "B applies_to A" ficariam indistinguíveis para quem
#: lê — e são afirmações opostas.
RELACOES: dict[str, dict[str, str]] = {
    "applies_to": {
        "pergunta": "onde este conceito se aplica na prática?",
        "direcao": "abstract_to_practical",
        "nao_significa": "não é 'menciona' nem 'tem a ver com': é a "
                         "declaração de que o conceito da ORIGEM governa o "
                         "caso do DESTINO",
    },
    "exemplifies": {
        "pergunta": "de que este caso é exemplo?",
        "direcao": "practical_to_abstract",
        "nao_significa": "não é 'prova': um exemplo não valida o conceito, "
                         "só o instancia — a inversa de `applies_to`, para "
                         "o curador escrever do lado em que está",
    },
    "refines": {
        "pergunta": "que ideia mais geral esta aqui detalha?",
        "direcao": "abstract_to_abstract",
        "nao_significa": "não é sucessão (`supersedes` aposenta; refinar "
                         "convive) nem contradição — as duas continuam "
                         "verdadeiras em níveis diferentes de detalhe",
    },
}


def e_relacao(nome: str | None) -> bool:
    """Pertence ao vocabulário? Usado no GATE DE ESCRITA."""
    return bool(nome) and nome in RELACOES


def relacao_ou_none(nome: str | None) -> str | None:
    """Leitura tolerante: fora do vocabulário ⇒ `None` (não tipada)."""
    return nome if e_relacao(nome) else None


def direcao(nome: str) -> str:
    return RELACOES[nome]["direcao"]


def inversa_de(nome: str) -> bool:
    """Relação que aponta do PRÁTICO para o abstrato — a que responde à
    mesma pergunta pelo outro lado."""
    return direcao(nome) == "practical_to_abstract"
