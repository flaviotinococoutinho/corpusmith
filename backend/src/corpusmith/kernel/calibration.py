"""Calibração de confiança (v0.18) — metacognição mensurável.

Brier, "Verification of forecasts expressed in terms of probability"
(Monthly Weather Review, 1950): a qualidade de um previsor probabilístico
é o erro quadrático médio entre confiança e desfecho,

    BS = (1/n) · Σ (p_i − o_i)²      ∈ [0, 1], menor é melhor.

Lichtenstein, Fischhoff & Phillips ("Calibration of probabilities",
1982) mostram o padrão humano típico: EXCESSO de confiança — a fração
de acertos fica abaixo da confiança média declarada. Aqui o previsor é
a própria memória: p = 1 − uncertainty da resposta fundida, o = 1 se o
desfecho foi `useful`. A curva de confiabilidade (bins) responde "quando
o sistema diz 80%, acerta 80%?" — e o gap alimenta observações
metacognitivas com gate humano (nunca rótulo automático).

Puro: stdlib somente.
"""
from __future__ import annotations

Pair = tuple[float, int]                 # (confiança ∈ [0,1], desfecho ∈ {0,1})


def brier_score(pairs: list[Pair]) -> float | None:
    """Erro quadrático médio; None sem dados (nunca 0 fingido)."""
    if not pairs:
        return None
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


def overconfidence(pairs: list[Pair]) -> float | None:
    """confiança média − taxa de acerto: >0 = excesso, <0 = falta."""
    if not pairs:
        return None
    n = len(pairs)
    return (sum(p for p, _ in pairs) - sum(o for _, o in pairs)) / n


def calibration_bins(pairs: list[Pair], bins: int = 5) -> list[dict]:
    """Curva de confiabilidade: por faixa de confiança, a confiança média
    versus a fração observada de acertos (bins vazios ficam de fora)."""
    buckets: list[list[Pair]] = [[] for _ in range(bins)]
    for p, o in pairs:
        index = min(bins - 1, int(max(0.0, min(1.0, p)) * bins))
        buckets[index].append((p, o))
    out = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        n = len(bucket)
        out.append({"lo": index / bins, "hi": (index + 1) / bins, "n": n,
                    "mean_confidence": sum(p for p, _ in bucket) / n,
                    "hit_rate": sum(o for _, o in bucket) / n})
    return out
