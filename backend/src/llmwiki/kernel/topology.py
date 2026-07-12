"""Topologia aplicada ao grafo de conhecimento (v0.9 · v1.1).

Homologia persistente 0-dimensional sobre a filtração descendente de pesos
(Edelsbrunner, Letscher & Zomorodian, "Topological Persistence and
Simplification", Discrete & Computational Geometry 2002): varremos as
arestas do peso mais alto ao mais baixo; cada aresta que UNE dois
componentes é um evento de morte na filtração. Arestas que unem componentes
GRANDES a pesos BAIXOS são as pontes frágeis da base — dois blocos de
conhecimento que só se falam por um fio fraco. É exatamente o diagnóstico
que interessa à curadoria ("linke mais estes dois temas"), obtido sem
nenhuma dependência além de union-find.

v1.1 (inspiração InfraNodus, solução própria): duas leituras de rede de
texto que o projeto ainda não tinha:
- CENTRALIDADE DE INTERMEDIAÇÃO (Brandes, "A Faster Algorithm for
  Betweenness Centrality", J. Math. Sociology 2001): o nó por onde passam
  os caminhos mais curtos é o articulador do discurso — não o mais citado
  (grau), o que LIGA blocos. Dá o "tamanho por influência" do grafo visual;
- LACUNA ESTRUTURAL: onde o InfraNodus vira ferramenta de ideação. A ponte
  frágil aponta o fio FRACO que existe; a lacuna aponta o fio AUSENTE. Dois
  blocos grandes que quase nunca se conectam são medidos pelo DÉFICIT sob o
  modelo de configuração (Newman) — a MESMA hipótese nula da modularidade
  que o Leiden já usa: sob fiação aleatória preservando graus, A e B
  compartilhariam (K_A·K_B)/2m arestas; se compartilham muito menos, há uma
  lacuna. O representante de cada lado é o nó de maior intermediação — os
  porta-vozes naturais para a pergunta-ponte "como A se relaciona com B?".
"""
from __future__ import annotations
from collections import defaultdict, deque
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


# ============================================ v1.1 — leitura de rede (InfraNodus)
def betweenness_centrality(
        edges: list[tuple[str, str, float]]) -> dict[str, float]:
    """Intermediação de Brandes (não-direcionada, caminhos mais curtos
    não-ponderados) normalizada em [0,1]. O articulador do discurso é o
    nó por onde passam mais geodésicas — quem LIGA, não quem é citado."""
    adjacency: dict[str, set[str]] = defaultdict(set)
    for src, dst, *_ in edges:
        if src != dst:
            adjacency[src].add(dst)
            adjacency[dst].add(src)
    nodes = list(adjacency)
    centrality = {v: 0.0 for v in nodes}
    for source in nodes:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {w: [] for w in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance = dict.fromkeys(nodes, -1)
        distance[source] = 0
        queue = deque([source])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adjacency[v]:
                if distance[w] < 0:
                    queue.append(w)
                    distance[w] = distance[v] + 1
                if distance[w] == distance[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != source:
                centrality[w] += delta[w]
    n = len(nodes)
    scale = (1.0 / ((n - 1) * (n - 2))) if n > 2 else 0.0   # /2 (undir) embutido
    return {v: round(c * scale, 6) for v, c in centrality.items()}


@dataclass(frozen=True)
class StructuralGap:
    """Fio AUSENTE: dois blocos (comunidades) que, sob o modelo de
    configuração, deveriam compartilhar `expected` arestas mas
    compartilham só `actual` — o `deficit` é o quanto falta. `rep_a`/
    `rep_b` são os articuladores (maior intermediação) de cada lado."""
    community_a: int
    community_b: int
    rep_a: str
    rep_b: str
    deficit: float
    expected: float
    actual: int


def structural_gaps(edges: list[tuple[str, str, float]],
                    community_of: dict[str, int],
                    betweenness: dict[str, float],
                    limit: int = 8,
                    min_size: int = 2) -> list[StructuralGap]:
    """Pares de comunidades com maior DÉFICIT de conexão vs. o esperado
    sob fiação aleatória preservando graus (a hipótese nula da
    modularidade). Só déficit > 0 (menos ligadas que o acaso) e
    comunidades com ≥ `min_size` nós entram."""
    degree: dict[str, float] = defaultdict(float)
    for src, dst, *w in edges:
        weight = w[0] if w else 1.0
        degree[src] += weight
        degree[dst] += weight
    total = sum(degree.values()) / 2.0 or 1.0
    community_degree: dict[int, float] = defaultdict(float)
    community_size: dict[int, int] = defaultdict(int)
    for node, comm in community_of.items():
        community_degree[comm] += degree.get(node, 0.0)
        community_size[comm] += 1
    inter: dict[tuple[int, int], float] = defaultdict(float)
    for src, dst, *w in edges:
        ca, cb = community_of.get(src), community_of.get(dst)
        if ca is None or cb is None or ca == cb:
            continue
        inter[(min(ca, cb), max(ca, cb))] += (w[0] if w else 1.0)
    representative: dict[int, str] = {}
    for node, comm in community_of.items():
        best = representative.get(comm)
        if best is None or betweenness.get(node, 0.0) > betweenness.get(best, 0.0):
            representative[comm] = node
    comms = sorted(c for c, size in community_size.items()
                   if size >= min_size and c in representative and c >= 0)
    gaps: list[StructuralGap] = []
    for i, ca in enumerate(comms):
        for cb in comms[i + 1:]:
            actual = inter.get((ca, cb), 0.0)
            expected = community_degree[ca] * community_degree[cb] / (2.0 * total)
            deficit = expected - actual
            if deficit <= 0:
                continue
            gaps.append(StructuralGap(
                ca, cb, representative[ca], representative[cb],
                round(deficit, 3), round(expected, 3), int(actual)))
    return sorted(gaps, key=lambda g: -g.deficit)[:limit]
