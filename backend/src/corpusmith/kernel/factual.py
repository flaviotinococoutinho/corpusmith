"""Conflito factual entre páginas — PURO (RFC-005, F4-PR3a).

**O que este módulo NÃO consegue fazer, e por que isso define o desenho.**
`docs/14` §P-5 pediu "mesma entidade de kind quantity com valores fora de
tolerância". Não é implementável como está:

    quantities.py:67      canonical = f"{value:g} {disp}"     # "250 ms"
    schema_index.sql:49   entities UNIQUE(kind, canonical)

O `canonical` de uma quantidade **é o valor**. Duas quantidades em conflito
são, por construção, entidades DIFERENTES — nunca "a mesma entidade com
valores diferentes". E não há coluna ligando uma quantidade ao SUJEITO de
que ela é predicado: o índice sabe que a página menciona `250 ms`, não que
ela afirma que algo dura 250 ms.

**Onde o sujeito vem, então.** Do grupo de identificador forte que
`policy.contradiction_candidate` já forma: duas páginas que citam o mesmo
DOI falam da mesma fonte. Este módulo recebe só as medidas DAQUELAS páginas
— quem monta o grupo é o shell. Duas páginas sem nada em comum que
mencionam `250 ms` não chegam aqui, e é essa restrição que impede a fila de
inundar (RFC-005 §3).

**Por que não importa `normalize`.** `normalize` é outro pacote puro, e o
núcleo não atravessa fronteira de pacote (teste de arquitetura). A entrada é
a forma mínima — dicts com `dim`/`si` — e o módulo fica testável sem disco,
sem gazetteer e sem detector.
"""
from __future__ import annotations

#: Tolerância RELATIVA sobre o valor SI de maior magnitude.
#:
#: PRIMEIRO limiar numérico do Harness — até aqui as regras usavam só
#: cardinalidades (`< 2`) e truncamentos de mensagem. Abaixo de 1% ficam
#: arredondamento de exibição e transcrição (`1.5 GB` e `1500 MB` são
#: idênticos em SI; `12.5 km` vs `12.51 km` é digitação); acima, a
#: divergência sobrevive a qualquer formatação razoável.
#:
#: **Não é calibrado.** Não existe golden set de conflitos factuais neste
#: repositório, e inventar um número e chamá-lo de calibrado seria a
#: alegação que ADR-53 §3 proíbe. É ponto de partida declarado — mesma
#: honestidade que `epistemics.toml` já aplica ao HI/LO da reconciliação.
TOLERANCIA_RELATIVA = 0.01

#: Dimensões que NUNCA produzem conflito, com o motivo:
#:
#: - `temp` — `quantities.py:65` suprime o payload `si` para temperatura
#:   (não há conversão afim °C↔°F). Sem SI não há comparação, e comparar
#:   valores brutos de escalas diferentes seria pior que não comparar;
#: - `ratio` — porcentagem não é dimensão física. `50%` numa página e `80%`
#:   noutra podem ser percentuais DE COISAS DIFERENTES; compará-los seria
#:   inventar o sujeito que o módulo inteiro se recusa a inventar.
EXCLUIDAS = ("temp", "ratio")


def _dispersao(valores: list[float]) -> float:
    """Dispersão relativa ao valor de maior magnitude. Zero quando todos os
    valores são zero — divisão protegida, sem caso especial no chamador."""
    maior, menor = max(valores), min(valores)
    escala = max(abs(maior), abs(menor))
    return 0.0 if escala == 0 else (maior - menor) / escala


def divergencias(medidas: dict[str, list[dict]], *,
                 tolerancia: float = TOLERANCIA_RELATIVA) -> list[dict]:
    """Conflitos factuais entre as páginas de UM grupo já relacionado.

    `medidas` é `{rel_path: [{"dim", "si", "unit", "surface", "span"}]}` —
    só quantidades com payload SI; o shell filtra antes de chamar.

    **A guarda de precisão que o plano não previa.** Uma dimensão só vira
    conflito se CADA página envolvida afirmar UM valor para ela. Uma página
    que menciona `12 km` e `20 km` está descrevendo faixa ou comparação, não
    afirmando um valor — comparar o extremo dela com o de outra página seria
    ler mal o texto. Precisão > recall, e o custo é declarado: faixa contra
    valor único não é detectada.

    Devolve uma entrada por DIMENSÃO em conflito, ordenada por dimensão para
    que a saída seja estável (o chamador põe isso em `meta`, que é contrato
    de fato da fila)."""
    por_dim: dict[str, dict[str, list[dict]]] = {}
    for pagina, itens in medidas.items():
        for m in itens:
            dim = m.get("dim")
            si = m.get("si")
            if not dim or dim in EXCLUIDAS or not isinstance(si, (int, float)):
                continue
            por_dim.setdefault(dim, {}).setdefault(pagina, []).append(m)

    out: list[dict] = []
    for dim in sorted(por_dim):
        paginas = por_dim[dim]
        if len(paginas) < 2:
            continue                      # divergência precisa de duas vozes
        afirmacoes: dict[str, dict] = {}
        for pagina, itens in paginas.items():
            distintos = {float(m["si"]) for m in itens}
            if len(distintos) != 1:
                afirmacoes = {}           # faixa: a dimensão inteira sai
                break
            afirmacoes[pagina] = itens[0]
        if len(afirmacoes) < 2:
            continue
        valores = [float(m["si"]) for m in afirmacoes.values()]
        espalhamento = _dispersao(valores)
        if espalhamento <= tolerancia:
            continue
        out.append({
            "dim": dim,
            "spread": round(espalhamento, 6),
            "tolerance": tolerancia,
            "pages": {p: {"si": float(m["si"]), "unit": m.get("unit"),
                          "surface": m.get("surface"), "span": m.get("span")}
                      for p, m in sorted(afirmacoes.items())},
        })
    return out


def resumo(divergencia: dict) -> str:
    """Uma linha legível para a mensagem do finding e para a fila.

    Mostra a SUPERFÍCIE como o texto a traz (`12 km`), não o valor SI: quem
    vai conferir procura no texto o que está escrito, não o convertido."""
    partes = ", ".join(
        f"{pagina} diz {dados.get('surface') or dados['si']}"
        for pagina, dados in divergencia["pages"].items())
    pct = divergencia["spread"] * 100
    return (f"divergência de {pct:.0f}% em {divergencia['dim']}: {partes} "
            f"(tolerância declarada: {divergencia['tolerance'] * 100:.0f}%)")
