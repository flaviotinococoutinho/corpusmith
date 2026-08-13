"""PythonComputeKernel — implementação de REFERÊNCIA e fallback
(ADR-39). Sempre disponível; delega para o kernel puro existente
(graphwalk/topology/sketch), preservando exatamente a matemática que os
golden/property tests já cobrem. O grafo carregado usa interning
(page path → u32) para cumprir o contrato da porta.
"""
from __future__ import annotations
import heapq
from typing import Sequence
from .. import __version__
from ..kernel.graphwalk import personalized_pagerank as _ppr_str
from ..kernel.sketch import bands, hamming, simhash
from ..kernel.topology import betweenness_centrality
from .types import BackendInfo, GraphHandle

# peso por confiança da aresta — MESMA tabela usada desde a v0.13
EDGE_WEIGHT = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}
GRAPH_ALGO_VERSION = "ppr-0.5/brandes-1"


def load_edges(idx) -> list[tuple[str, str, float]]:
    """Arestas ponderadas do index.db (uma consulta; sem N+1)."""
    return [(r[0], r[1], EDGE_WEIGHT.get(r[2], 0.5)) for r in idx.execute(
        "SELECT src, dst, COALESCE(confidence,'extracted') "
        "FROM graph_edges")]


def graph_generation(idx) -> str:
    rows = dict(idx.execute(
        "SELECT key, value FROM index_meta WHERE key IN "
        "('bundle_head','index_generation')").fetchall())
    return f"{rows.get('bundle_head', '')}:{rows.get('index_generation', '')}"


class PythonComputeKernel:
    def backend_info(self) -> BackendInfo:
        return BackendInfo(name="python", version=__version__)

    # ------------------------------------------------------------ grafo
    def load_graph(self, *, index_path: str, connection=None) -> GraphHandle:
        from ..runtime.db import connect
        idx = connection or connect(index_path)
        try:
            edge_rows = load_edges(idx)
            generation = graph_generation(idx)
        finally:
            if connection is None:
                idx.close()
        # interning: path → id (determinístico por ordem de aparição)
        page_id: dict[str, int] = {}
        for src, dst, _ in edge_rows:
            page_id.setdefault(src, len(page_id))
            page_id.setdefault(dst, len(page_id))
        adjacency: dict[str, dict[str, float]] = {}
        for src, dst, weight in edge_rows:
            adjacency.setdefault(src, {})
            adjacency.setdefault(dst, {})
            adjacency[src][dst] = adjacency[src].get(dst, 0.0) + weight
            adjacency[dst][src] = adjacency[dst].get(src, 0.0) + weight
        pages = tuple(page_id)                    # id i == posição i
        return GraphHandle(backend="python", generation=generation,
                           nodes=len(pages), edges=len(edge_rows),
                           pages=pages,
                           native={"adjacency": adjacency,
                                   "edge_rows": edge_rows})

    def personalized_pagerank(self, graph: GraphHandle,
                              seeds: dict[str, float], *,
                              damping: float = 0.5, iterations: int = 20,
                              tolerance: float = 1e-6,
                              top_k: int = 12) -> list[tuple[str, float]]:
        rank = _ppr_str(graph.native["adjacency"], seeds, damping=damping,
                        iterations=iterations, tolerance=tolerance)
        top = heapq.nlargest(top_k, rank.items(), key=lambda kv: kv[1]) \
            if top_k else sorted(rank.items(), key=lambda kv: -kv[1])
        return [(page, score) for page, score in top]

    def betweenness(self, graph: GraphHandle, *,
                    top_k: int = 0) -> dict[str, float]:
        centrality = betweenness_centrality(graph.native["edge_rows"])
        if top_k:
            best = heapq.nlargest(top_k, centrality.items(),
                                  key=lambda kv: kv[1])
            return dict(best)
        return centrality

    def components(self, graph: GraphHandle) -> list[int]:
        """Rótulo de componente por nó (índice = page id); rótulo =
        menor page id do componente (critério determinístico)."""
        parent = list(range(graph.nodes))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        index = {page: i for i, page in enumerate(graph.pages)}
        for src, dst, _ in graph.native["edge_rows"]:
            ra, rb = find(index[src]), find(index[dst])
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        return [find(i) for i in range(graph.nodes)]

    # ----------------------------------------------------------- sketch
    def simhash_batch(self, texts: Sequence[str], *,
                      shingle: int = 3) -> list[int]:
        return [simhash(t, shingle=shingle) for t in texts]

    def consolidation_candidates(
            self, sketches: Sequence[int], *,
            max_hamming: int = 8) -> list[tuple[int, int]]:
        """Pares (i<j) com hamming ≤ max_hamming, via bandas LSH (EXATO
        por casa de pombos com 9 bandas p/ limiar 8) + verificação."""
        buckets: dict[tuple, list[int]] = {}
        for i, sk in enumerate(sketches):
            for band in bands(sk):
                buckets.setdefault(band, []).append(i)
        seen: set[tuple[int, int]] = set()
        for members in buckets.values():
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    pair = (members[a], members[b])
                    if pair not in seen and \
                            hamming(sketches[pair[0]],
                                    sketches[pair[1]]) <= max_hamming:
                        seen.add(pair)
        return sorted(seen)
