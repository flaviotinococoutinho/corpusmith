"""Suficiência de evidência (P-4, ADR-52) — o selo 2D ao lado da dispersão.

`uncertainty` mede DISPERSÃO da fusão e zera quando a base é rasa —
certeza máxima no momento mais fraco. `support` responde a pergunta que
ela não responde: QUANTA evidência sustenta a resposta, em quatro
parcelas normalizadas [0, 1]:

- `distinct_pages`  — páginas distintas servidas (satura em 3);
- `corroborating_streams` — streams que trouxeram a evidência (satura
  em 3; a proveniência já existia para o crédito Hedge);
- `grounded_fraction` — fração da evidência com span aterrado (v1.8);
- `freshness` — fração nem stale nem superseded.

As saturações são LIMIARES DE PROJETO, não calibrados — o contrato
`evidence_sufficiency` os declara e a porta de reentrada do ADR-52 é
calibrá-los contra o golden. Núcleo PURO: stdlib, zero I/O.
"""
from __future__ import annotations

_PAGES_SATURATION = 3
_STREAMS_SATURATION = 3


def evidence_support(distinct_pages: int, corroborating_streams: int,
                     grounded_fraction: float,
                     fresh_fraction: float) -> dict:
    components = {
        "distinct_pages": min(1.0, distinct_pages / _PAGES_SATURATION),
        "corroborating_streams": min(
            1.0, corroborating_streams / _STREAMS_SATURATION),
        "grounded_fraction": max(0.0, min(1.0, grounded_fraction)),
        "freshness": max(0.0, min(1.0, fresh_fraction)),
    }
    score = round(sum(components.values()) / len(components), 4)
    return {"score": score,
            "components": {k: round(v, 4) for k, v in components.items()}}


def empty_support() -> dict:
    """Abstenção/base vazia: shape idêntico, tudo zero — a ausência de
    evidência não pode parecer um caso especial para o consumidor."""
    return evidence_support(0, 0, 0.0, 0.0)
