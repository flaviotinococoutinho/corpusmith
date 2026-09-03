"""Dificuldade de explicar: onde o estudo trava — PURO (RFC-006, V4).

**A pergunta que este módulo responde**, e que nenhuma superfície do
produto respondia: *entre as páginas que já tenho, quais são as mais
difíceis de explicar?* Quem acumula muito conteúdo não trava por falta
de material — trava em pontos específicos, e eles ficavam espalhados por
cinco donos que nunca se olhavam: a falha de recuperação com
sobreconfiança (`cognitive/practice.py`), a contradição e o conflito
factual (`harness/local_policy.py`), a pergunta que ninguém respondeu, o
vocabulário ainda ambíguo (V2) e a lacuna que reincide (`ask_misses`, F6).

**Composição, não detector novo.** Todos os sinais já existem e cada um
tem dono; aqui só se soma, com pesos FIXOS e declarados no contrato
`explanation_difficulty`. É o molde do `attention_queue`: peso de projeto,
não aprendido, e `test_epistemics_toml` amarra estes números aos do TOML.

**Três recusas deliberadas**, cada uma com teste que a prende:

1. **`low_yield` fica FORA.** É a armadilha que a RFC-006 nomeou: somar
   "ninguém achou útil" com "é difícil de explicar" re-fundiria o que o
   F4-PR2 gastou uma fase separando. Página impopular pode ser
   cristalina; página muito lida pode ser a mais espinhosa.
2. **Silêncio não é facilidade.** Sem nenhum sinal, o resultado é
   `medida=False` — não "fácil". A ausência de prática, de conflito e de
   pergunta diz que ninguém olhou, não que está resolvido (a mesma
   disciplina do `measurable=false` da profundidade, v0.20).
3. **A saturação impede o componente único.** Uma sessão de prática ruim
   produziria dezenas de falhas confiantes e afogaria os outros quatro
   sinais; cada componente satura no seu teto declarado e vale, no
   máximo, o próprio peso.

**Nível, dito em voz alta** (docs/28 §2): o índice é por PÁGINA e fala de
compreensão de AFIRMAÇÕES. Enquanto o nível 3 da escada não existir, essa
diferença é aproximação declarada — não precisão fingida.
"""
from __future__ import annotations
from dataclasses import dataclass, field

#: Os cinco componentes, com o dono de cada sinal:
#: - `falha_confiante`      prática humana  (retrieval_attempts, human_feedback)
#: - `conflito`             harness         (contradiction/factual_conflict)
#: - `pergunta_aberta`      bundle          (type=question sem answered_by)
#: - `vocabulario_ambiguo`  gazetteer/V2    (policy.alias_conflict)
#: - `lacuna_recorrente`    F6              (ask_misses aberto e reincidente)
COMPONENTES = ("falha_confiante", "conflito", "pergunta_aberta",
               "vocabulario_ambiguo", "lacuna_recorrente")

#: Pesos de PROJETO (somam 1.0), não calibrados — o contrato os declara e
#: a porta de reentrada é medi-los contra desfechos de prática reais. A
#: ordem expressa uma tese: o sinal humano (alguém tentou explicar e
#: falhou achando que sabia) vale mais que qualquer sinal derivado.
PESOS = {"falha_confiante": 0.35,
         "conflito": 0.25,
         "pergunta_aberta": 0.15,
         "vocabulario_ambiguo": 0.15,
         "lacuna_recorrente": 0.10}

#: Teto de cada componente: a partir daqui ele vale o peso inteiro. São
#: limiares de projeto (como as saturações do `evidence_sufficiency`),
#: escolhidos baixos de propósito — três falhas confiantes sobre a mesma
#: página já dizem tudo o que a quarta diria.
SATURACAO = {"falha_confiante": 3,
             "conflito": 2,
             "pergunta_aberta": 2,
             "vocabulario_ambiguo": 2,
             "lacuna_recorrente": 3}

_ROTULO = {"falha_confiante": "falha de recuperação com confiança alta",
           "conflito": "conflito/contradição por resolver",
           "pergunta_aberta": "pergunta aberta apontando para cá",
           "vocabulario_ambiguo": "vocabulário ainda ambíguo",
           "lacuna_recorrente": "a base já se absteve sobre este assunto"}


@dataclass(frozen=True)
class Dificuldade:
    """Score COM decomposição e motivo — nunca um número solto.

    `medida` é o campo que impede a leitura errada mais provável: `score`
    0.0 com `medida=False` significa "nada observado", e é diferente de
    0.0 com `medida=True`, que significaria "observado e sem atrito"
    (hoje inalcançável: qualquer sinal soma > 0, e o teste diz isso)."""
    rel_path: str = ""
    score: float = 0.0
    medida: bool = False
    motivo: str = ""
    componentes: dict[str, float] = field(default_factory=dict)


def dificuldade(sinais: dict[str, int], *, rel_path: str = "") -> Dificuldade:
    """Compõe os sinais de UMA página.

    Chave desconhecida é ERRO, não ruído ignorado: um componente novo tem
    de passar por peso, saturação e contrato — entrar de carona por um
    `dict` seria exatamente a heurística sem dono que o registro
    epistêmico existe para impedir."""
    for nome, n in sinais.items():
        if nome not in PESOS:
            raise ValueError(
                f"componente desconhecido: {nome!r} — declare peso, "
                f"saturação e contrato antes (válidos: {list(COMPONENTES)})")
        if int(n) < 0:
            raise ValueError(f"contagem negativa em {nome!r}: {n}")

    componentes = {c: round(PESOS[c] * min(1.0, int(sinais.get(c, 0))
                                           / SATURACAO[c]), 4)
                   for c in COMPONENTES}
    score = round(sum(componentes.values()), 4)
    observados = [c for c in COMPONENTES if int(sinais.get(c, 0)) > 0]
    if not observados:
        motivo = ("sem sinal — ninguém praticou, nada conflita e nada "
                  "ficou perguntado; NÃO é o mesmo que fácil")
    else:
        dominante = max(observados, key=lambda c: componentes[c])
        extras = len(observados) - 1
        motivo = _ROTULO[dominante] + (f" (+{extras} outro(s) sinal(is))"
                                       if extras else "")
    return Dificuldade(rel_path=rel_path, score=score, medida=bool(observados),
                       motivo=motivo, componentes=componentes)


def consolidar(por_pagina: dict[str, dict[str, int]]) -> list[Dificuldade]:
    """Ranking do mais difícil para o menos, desempatado por caminho.

    O desempate não é estético: sem ele a projeção mudaria de ordem entre
    execuções com a mesma entrada, e comparar duas leituras deixaria de
    ser possível — a mesma razão do seed fixo do particionamento."""
    return sorted((dificuldade(sinais, rel_path=rel)
                   for rel, sinais in por_pagina.items()),
                  key=lambda d: (-d.score, d.rel_path))
