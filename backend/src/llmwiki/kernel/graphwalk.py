"""Personalized PageRank (v0.13) — associatividade multi-hop no grafo.

Gutiérrez et al., "HippoRAG: Neurobiologically Inspired Long-Term Memory
for Large Language Models" (NeurIPS 2024, arXiv:2405.14831): retrieval
multi-hop via Personalized PageRank semeado pelas entidades da pergunta —
o análogo computacional da separação de padrões do hipocampo. Um fato em
B, ligado a A que menciona a entidade perguntada, é alcançável mesmo que
B não compartilhe NENHUM termo com a pergunta.

Aqui: power iteration pura sobre dicts (o grafo local cabe em memória),
damping 0.5 como no paper — mais massa presa aos seeds, caminhada curta:
associação, não deriva.
"""
from __future__ import annotations


def personalized_pagerank(adjacency: dict[str, dict[str, float]],
                          seeds: dict[str, float], *,
                          damping: float = 0.5, iterations: int = 20,
                          tolerance: float = 1e-6) -> dict[str, float]:
    """p ← (1−d)·s + d·Wᵀp, com W normalizado por linha e s = seeds
    normalizados. Devolve score por nó (soma 1). Seeds fora do grafo
    contribuem massa de reinício mesmo sem arestas."""
    nodes = set(adjacency) | {n for nb in adjacency.values() for n in nb} \
        | set(seeds)
    total_seed = sum(w for w in seeds.values() if w > 0)
    if not nodes or total_seed <= 0:
        return {}
    restart = {n: seeds.get(n, 0.0) / total_seed for n in nodes}
    out_weight = {n: sum(adjacency.get(n, {}).values()) for n in nodes}
    rank = dict(restart)
    for _ in range(iterations):
        incoming: dict[str, float] = {n: 0.0 for n in nodes}
        for source, neighbors in adjacency.items():
            if out_weight[source] <= 0:
                continue
            spread = rank.get(source, 0.0) / out_weight[source]
            for target, weight in neighbors.items():
                incoming[target] += spread * weight
        dangling = sum(rank[n] for n in nodes if out_weight[n] <= 0)
        updated = {n: (1 - damping) * restart[n]
                   + damping * (incoming[n] + dangling * restart[n])
                   for n in nodes}
        delta = sum(abs(updated[n] - rank[n]) for n in nodes)
        rank = updated
        if delta < tolerance:
            break
    return rank
