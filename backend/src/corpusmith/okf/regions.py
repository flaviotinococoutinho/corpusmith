"""Regiões sentineladas no corpo — a primitiva (F1-PR5).

O F1-PR4 estabeleceu a regra de proveniência do eixo humano: **por região,
não por elemento**. Tudo entre as sentinelas é território do ato; tudo fora
é do autor, e o ato não olha. `okf/relations.py` foi o primeiro cliente
dessa regra e trouxe a guarda que só um defeito medido ensina — contar
SENTINELAS, não blocos casados, porque com regex guloso uma sentinela de
fechamento apagada à mão faz o bloco casar por cima da prosa do meio e a
re-renderização a APAGA.

O `MergePages` precisa da mesma regra com uma diferença: relações são UM
bloco por página, e absorções são N — uma por página fundida, cada qual
declarando sua origem. Escrever a contagem de sentinelas de novo seria
repetir, no ato de reusá-la, exatamente o erro que o PR4 corrigiu (duas
cópias do `MD_LINK` divergindo em silêncio). Então a guarda mora aqui, uma
vez, e os dois módulos a chamam.

O que esta camada garante e o que não garante:

- garante que qualquer estado ambíguo de sentinela **recusa** com motivo
  nomeado, em vez de re-renderizar por cima de conteúdo do autor;
- garante que sentinela dentro de cerca de código é IGNORADA (a primeira
  vítima seria a página que documenta esta feature);
- **não** decide o que vai dentro da região — isso é do módulo cliente,
  porque a política de conteúdo (texto de entrada, título, ordem) é
  específica do ato.
"""
from __future__ import annotations
import re
from ..normalize.masking import is_protected, protected_spans


class RegiaoInconsistente(ValueError):
    """Sentinelas em estado que o ato não sabe manter sem risco."""


def _livres(body: str, rx: re.Pattern, protegidas) -> list[re.Match]:
    return [m for m in rx.finditer(body)
            if not is_protected(protegidas, m.start(), m.end())]


def blocks(body: str, abre: re.Pattern, fecha: re.Pattern, *,
           nome: str, maximo: int | None = None) -> list[re.Match]:
    """Regiões `[abre … fecha]` do corpo, em ordem de posição.

    Devolve a lista de matches da ABERTURA (o cliente costuma precisar dos
    grupos capturados nela); o fim de cada região é `spans()[i][1]`. Os
    regexes MUST estar ancorados em linha (`^…$` com `re.M`), senão uma
    menção em prosa viraria sentinela.

    Recusa — sem tocar em nada — qualquer estado que não seja um número
    igual de aberturas e fechamentos em ALTERNÂNCIA estrita: é o único
    jeito de garantir que re-renderizar não engula conteúdo do autor.
    """
    protegidas = protected_spans(body)
    abres = _livres(body, abre, protegidas)
    fechas = _livres(body, fecha, protegidas)
    if len(abres) != len(fechas):
        raise RegiaoInconsistente(
            f"{nome} inconsistente: {len(abres)} abertura(s) e "
            f"{len(fechas)} fechamento(s). "
            "Edite a página à mão para deixar pares completos — o ato não "
            "mexe em corpo ambíguo.")
    if maximo is not None and len(abres) > maximo:
        raise RegiaoInconsistente(
            f"{nome} inconsistente: {len(abres)} regiões, no máximo "
            f"{maximo} esperada(s).")
    # alternância estrita: abre, fecha, abre, fecha… Qualquer outra ordem
    # (aninhado, fechamento antes da abertura, dois abres seguidos) é
    # ambígua mesmo com contagens iguais.
    ordem = sorted([(m.start(), 0) for m in abres]
                   + [(m.start(), 1) for m in fechas])
    for i, (_, tipo) in enumerate(ordem):
        if tipo != i % 2:
            raise RegiaoInconsistente(
                f"{nome} inconsistente: sentinelas fora de ordem "
                "(aninhadas ou fechamento "
                "antes da abertura) — o ato não mexe em corpo ambíguo.")
    return abres


def spans(body: str, abre: re.Pattern, fecha: re.Pattern, *,
          nome: str, maximo: int | None = None) -> list[tuple[int, int]]:
    """`[(início, fim)]` de cada região, já validadas por `blocks`."""
    protegidas = protected_spans(body)
    abres = blocks(body, abre, fecha, nome=nome, maximo=maximo)
    fechas = _livres(body, fecha, protegidas)
    return [(a.start(), f.end()) for a, f in zip(abres, fechas)]


def without(body: str, faixas: list[tuple[int, int]]) -> str:
    """Corpo sem as faixas dadas (da última para a primeira, para os
    offsets não se invalidarem)."""
    out = body
    for inicio, fim in sorted(faixas, reverse=True):
        out = out[:inicio] + out[fim:]
    return out.rstrip("\n")
