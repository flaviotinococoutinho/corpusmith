"""RustComputeKernel — acelerador via extensão PyO3 `llmwiki_native`
(ADR-39). Tradução fina: interning e SQL ficam em Python; o trabalho
CPU-bound (PPR sobre CSR, Brandes, SimHash em lote, pares candidatos)
roda em Rust com o GIL liberado. Resultados voltam como SoA (listas
paralelas), nunca list[dict] gigante.

Semântica de seeds FORA do grafo (paridade com kernel.graphwalk): a
massa de restart delas é agregada num único nó virtual sem arestas —
matematicamente equivalente para os scores dos nós reais (nós isolados
só interagem via soma de dangling).
"""
from __future__ import annotations
import heapq
from typing import Sequence
from .python_kernel import graph_generation, load_edges
from .types import BackendInfo, GraphHandle

PROTOCOL_VERSION = 1


def native_module():
    import llmwiki_native
    return llmwiki_native


class RustComputeKernel:
    def __init__(self):
        self._native = native_module()
        info = self._native.backend_info()
        if info.get("protocol") != PROTOCOL_VERSION:
            raise RuntimeError(
                f"llmwiki_native protocolo {info.get('protocol')} ≠ "
                f"{PROTOCOL_VERSION} esperado — atualize a extensão")
        self._info = info

    def backend_info(self) -> BackendInfo:
        return BackendInfo(name="rust", version=self._info["version"],
                           build=self._info.get("build", ""))

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
        page_id: dict[str, int] = {}
        for src, dst, _ in edge_rows:
            page_id.setdefault(src, len(page_id))
            page_id.setdefault(dst, len(page_id))
        sources = [page_id[s] for s, _, _ in edge_rows]
        targets = [page_id[d] for _, d, _ in edge_rows]
        weights = [w for _, _, w in edge_rows]
        graph = self._native.build_graph(sources, targets, weights,
                                         len(page_id))
        return GraphHandle(backend="rust", generation=generation,
                           nodes=len(page_id), edges=len(edge_rows),
                           pages=tuple(page_id),
                           native={"graph": graph, "index": page_id})

    def personalized_pagerank(self, graph: GraphHandle,
                              seeds: dict[str, float], *,
                              damping: float = 0.5, iterations: int = 20,
                              tolerance: float = 1e-6,
                              top_k: int = 12) -> list[tuple[str, float]]:
        index = graph.native["index"]
        inside_ids, inside_w, outside = [], [], 0.0
        for page, weight in seeds.items():
            if weight <= 0:
                continue
            if page in index:
                inside_ids.append(index[page])
                inside_w.append(float(weight))
            else:
                outside += float(weight)
        if not inside_ids and outside <= 0:
            return []
        ids, scores = graph.native["graph"].ppr(
            inside_ids, inside_w, outside, damping, iterations,
            tolerance, top_k)
        pages = graph.pages
        return [(pages[i], s) for i, s in zip(ids, scores)]

    def betweenness(self, graph: GraphHandle, *,
                    top_k: int = 0) -> dict[str, float]:
        ids, scores = graph.native["graph"].brandes(top_k)
        pages = graph.pages
        result = {pages[i]: s for i, s in zip(ids, scores)}
        if top_k:
            best = heapq.nlargest(top_k, result.items(),
                                  key=lambda kv: kv[1])
            return dict(best)
        return result

    def components(self, graph: GraphHandle) -> list[int]:
        return list(graph.native["graph"].components())

    # ----------------------------------------------------------- sketch
    def simhash_batch(self, texts: Sequence[str], *,
                      shingle: int = 3) -> list[int]:
        return list(self._native.simhash64_batch(list(texts), shingle))

    def consolidation_candidates(
            self, sketches: Sequence[int], *,
            max_hamming: int = 8) -> list[tuple[int, int]]:
        a_ids, b_ids = self._native.candidate_pairs64(list(sketches),
                                                      max_hamming)
        return sorted(zip(a_ids, b_ids))
