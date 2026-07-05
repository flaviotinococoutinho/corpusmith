"""Topologia aplicada ao grafo de conhecimento (v0.9).

Homologia persistente 0-dimensional sobre a filtração descendente de pesos
(Edelsbrunner, Letscher & Zomorodian, "Topological Persistence and
Simplification", Discrete & Computational Geometry 2002): varremos as
arestas do peso mais alto ao mais baixo; cada aresta que UNE dois
componentes é um evento de morte na filtração. Arestas que unem componentes
GRANDES a pesos BAIXOS são as pontes frágeis da base — dois blocos de
conhecimento que só se falam por um fio fraco. É exatamente o diagnóstico
que interessa à curadoria ("linke mais estes dois temas"), obtido sem
nenhuma dependência além de union-find.
"""
from __future__ import annotations
from dataclasses import dataclass


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}
        self._size: dict[str, int] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        self._size.setdefault(x, 1)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:                 # path compression
            self._parent[x], x = root, self._parent[x]
        return root

    def size(self, x: str) -> int:
        return self._size[self.find(x)]

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]
        return True


@dataclass(frozen=True)
class MergeEvent:
    """Evento de morte na filtração: a aresta (src,dst) uniu, no peso
    `weight`, dois componentes de tamanhos `small_side` ≤ `large_side`."""
    src: str
    dst: str
    weight: float
    small_side: int
    large_side: int

    @property
    def is_bridge(self) -> bool:
        """Ponte estrutural: ambos os lados eram subgrafos reais (≥2 nós)."""
        return self.small_side >= 2


def component_persistence(
        edges: list[tuple[str, str, float]]) -> list[MergeEvent]:
    """Persistência 0-dim sobre a filtração descendente de pesos.
    Devolve os eventos de fusão em ordem de varredura (peso desc);
    filtre por `.is_bridge` e ordene por peso ASC para achar os fios
    mais frágeis entre os blocos mais substanciais."""
    forest = _UnionFind()
    events: list[MergeEvent] = []
    for src, dst, weight in sorted(edges, key=lambda e: -e[2]):
        size_a, size_b = forest.size(src), forest.size(dst)
        if forest.union(src, dst):
            events.append(MergeEvent(src, dst, weight,
                                     min(size_a, size_b),
                                     max(size_a, size_b)))
    return events


def fragile_bridges(edges: list[tuple[str, str, float]],
                    limit: int = 10) -> list[MergeEvent]:
    """As `limit` pontes mais frágeis: fusões de blocos reais, do peso
    mais baixo (mais frágil) para cima."""
    bridges = [e for e in component_persistence(edges) if e.is_bridge]
    return sorted(bridges, key=lambda e: e.weight)[:limit]
