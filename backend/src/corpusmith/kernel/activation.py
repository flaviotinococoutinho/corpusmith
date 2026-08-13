"""Ativação de nível base do ACT-R (v0.10).

Anderson & Schooler, "Reflections of the Environment in Memory"
(Psychological Science, 1991) mostram que a probabilidade de precisar de
uma memória segue lei de potência do histórico de uso; Anderson et al.,
"An Integrated Theory of the Mind" (Psychological Review, 2004) a
formalizam como Base-Level Activation:

    B_i = ln( Σ_j t_j^(−d) )

Guardar todos os timestamps de acesso é caro; a aproximação de
APRENDIZADO OTIMIZADO (assumindo acessos uniformemente distribuídos na
vida L da memória) é a forma padrão em implementações ACT-R:

    B ≈ ln( n / (1 − d) ) − d·ln(L)

com n = número de usos, L = idade da memória, d = 0.5 (o decay canônico).
Diferente do decaimento exponencial sobre o ÚLTIMO acesso (v0.8), o BLA
captura o efeito de espaçamento: 10 usos ao longo de 3 meses valem mais
que 10 usos num único dia antigo.
"""
from __future__ import annotations
import math

DECAY = 0.5                      # d canônico do ACT-R
_MIN_AGE_DAYS = 1.0 / 24.0       # 1h — evita explosão em memórias novíssimas


def base_level_activation(uses: int, age_days: float,
                          decay: float = DECAY) -> float:
    """B ≈ ln(n/(1−d)) − d·ln(L). Sem usos ⇒ −inf (nunca ativada)."""
    if uses <= 0:
        return float("-inf")
    age = max(age_days, _MIN_AGE_DAYS)
    return math.log(uses / (1.0 - decay)) - decay * math.log(age)


def logistic(x: float) -> float:
    """σ(x) ∈ (0,1) — mapeia a ativação (escala log, pode ser negativa)
    para um score comparável entre páginas. σ(−inf) = 0."""
    if x == float("-inf"):
        return 0.0
    x = max(-60.0, min(60.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def retrieval_probability(activation: float, *, tau: float = 0.0,
                          noise: float = 0.4) -> float:
    """Equação de recuperação do ACT-R (Anderson et al. 2004):

        P(recall) = 1 / (1 + e^((τ − B)/s))

    τ é o limiar de recuperação e s o ruído da ativação. É o critério
    VALIDADO de esquecimento (v0.12): uma memória é candidata à base fria
    quando P(recall) cai abaixo do corte — ou seja, quando o próprio
    modelo cognitivo prevê que ela não seria recuperada. B = −inf ⇒ P = 0."""
    if activation == float("-inf"):
        return 0.0
    return logistic((activation - tau) / max(noise, 1e-6))
