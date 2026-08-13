"""Vitalidade: o que ainda merece atenção — PURO (F3-PR2, P-3).

**O problema que este módulo nomeia.** As fontes da fila propunham trabalho
sobre páginas que já não existem. Medido nesta árvore, antes da correção:

    review_items -> ['concepts/apagada.md', 'concepts/morta.md',
                     'concepts/viva.md']

`concepts/morta.md` tinha `superseded_by` — foi aposentada por um ato humano
explícito — e `concepts/apagada.md` **nunca existiu no bundle**: `page_heat`
guarda o histórico de uso por caminho e ninguém o confronta com a autoridade.
A fila oferecia ao usuário revisar o que ele mesmo já tinha resolvido, e o
custo não é só ruído: é a fila perder credibilidade justo onde ela pede
confiança para ordenar a atenção.

**Por que a regra mora aqui e não em cada fonte.** Ela já estava implícita e
DIVERGENTE: `gap_items` iterava `iter_concepts()` (só páginas existentes, mas
sem olhar sucessão), `review_items` lia `page_heat` cru, `bridge_items` lia
`graph_bridges` cru. Três fontes, três respostas para "esta página conta?".
Uma definição só, testável sem tocar disco, é o que impede a quarta fonte de
inventar a quarta resposta.

**Aposentar não é apagar.** Uma página sucedida continua no bundle, no Git e
no índice — ela só deixa de ser *endereço de trabalho novo*. O estado derivado
dela (calor, agendamento de revisão) sobrevive intacto; o que muda é que a
fila para de propô-la. É a mesma disciplina do `until` dos vereditos: suprimir
com motivo, jamais DELETE.
"""
from __future__ import annotations

# Chaves de frontmatter que APOSENTAM uma página como alvo de trabalho novo.
# `invalid_at` é bi-temporal (deixou de valer no mundo) e `superseded_by` é
# sucessão declarada; ambas são gestos humanos registrados, não inferências.
APOSENTAM = ("superseded_by", "invalid_at")


def aposentada(meta: dict) -> str | None:
    """Motivo pelo qual esta página não é alvo de trabalho novo, ou None.

    Devolve o MOTIVO em vez de um booleano porque a fila precisa dizer por
    que não propôs — "sumiu da lista" sem explicação é indistinguível de
    defeito, e foi assim que o filtro ausente passou despercebido."""
    for chave in APOSENTAM:
        if meta.get(chave):
            return chave
    return None


def vivas(paginas: dict[str, dict]) -> set[str]:
    """Subconjunto de `{rel_path: frontmatter}` que ainda aceita trabalho."""
    return {rel for rel, meta in paginas.items() if aposentada(meta) is None}


def filtrar(itens: list[dict], vivas_: set[str], *,
            campo: str = "target") -> list[dict]:
    """Itens de fila cujo alvo está vivo.

    Item sem o campo de alvo passa: a regra é sobre PÁGINA, e uma fonte que
    proponha algo sem alvo de página (uma fonte em `raw/`, por exemplo) não
    deve sumir por um filtro que não a descreve."""
    return [i for i in itens
            if not i.get(campo) or i[campo] in vivas_]
