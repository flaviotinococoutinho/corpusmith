"""Teoria da informação aplicada à coordenação da memória (v0.9).

Três resultados clássicos, três usos no projeto:

- Cilibrasi & Vitányi, "Clustering by Compression" (IEEE Trans. Information
  Theory, 2005): a Normalized Compression Distance aproxima a distância de
  Kolmogorov com um compressor real. Aqui: sinal DETERMINÍSTICO de
  similaridade textual no reconciliador — sem modelo, sem embedding.

- Shannon (1948): entropia da distribuição de scores fundidos como medida
  de INCERTEZA do retrieval (parente do "semantic entropy" de Kuhn et al.,
  2023): massa de score espalhada ⇒ o sistema não sabe onde está a resposta
  — sinal para abstenção/hedging. Surprisal (−log p) pondera entidades
  raras acima das onipresentes (é o IDF com a roupa original).

- Freund & Schapire, "A decision-theoretic generalization of on-line
  learning" (JCSS, 1997): Hedge/multiplicative weights. Cada stream de
  retrieval (fts, dense, entity, descend) é um "expert"; os desfechos
  useful/dead_end são as perdas; os pesos convergem para os streams que
  historicamente acertam — com arrependimento sublinear garantido.
"""
from __future__ import annotations
import math
import zlib


def shannon_entropy(weights: list[float]) -> float:
    """Entropia NORMALIZADA [0,1] de uma distribuição de pesos positivos.
    0 = toda a massa num item (certeza); 1 = uniforme (incerteza máxima)."""
    positive = [w for w in weights if w > 0]
    if len(positive) < 2:
        return 0.0
    total = sum(positive)
    probabilities = [w / total for w in positive]
    h = -sum(p * math.log2(p) for p in probabilities)
    return h / math.log2(len(probabilities))


def ncd(a: str | bytes, b: str | bytes) -> float:
    """Normalized Compression Distance (Cilibrasi & Vitányi 2005):
    NCD(x,y) = (C(xy) − min(C(x),C(y))) / max(C(x),C(y)).
    ~0 para textos que se explicam mutuamente; ~1 para independentes."""
    xa = a.encode() if isinstance(a, str) else a
    xb = b.encode() if isinstance(b, str) else b
    if not xa or not xb:
        return 1.0
    ca = len(zlib.compress(xa, 6))
    cb = len(zlib.compress(xb, 6))
    cab = len(zlib.compress(xa + xb, 6))
    return max(0.0, (cab - min(ca, cb)) / max(ca, cb))


def surprisal(document_frequency: int, corpus_size: int) -> float:
    """Conteúdo de informação de Shannon −log2 p(e) de uma entidade que
    aparece em `document_frequency` de `corpus_size` páginas. Entidade
    onipresente informa ~0 bits; entidade rara informa muitos."""
    if corpus_size <= 0:
        return 0.0
    probability = min(1.0, max(document_frequency, 1) / corpus_size)
    return -math.log2(probability)


def hedge(weights: dict[str, float], losses: dict[str, float],
          *, eta: float = 0.25, floor: float = 0.5,
          ceiling: float = 2.0) -> dict[str, float]:
    """Um passo do algoritmo Hedge (Freund & Schapire 1997):
    w ← w·exp(−η·loss), com clamp [floor, ceiling] para que nenhum stream
    seja silenciado para sempre (o mundo muda; o clamp preserva exploração)."""
    updated = {}
    for expert, weight in weights.items():
        loss = losses.get(expert, 0.0)
        updated[expert] = min(ceiling, max(floor, weight * math.exp(-eta * loss)))
    return updated
