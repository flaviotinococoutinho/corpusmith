"""Tipos da porta ComputeKernel (ADR-39) — fechados e pequenos.

Interoperabilidade (regra da spec): resultados pequenos atravessam como
tipos Python simples (tuplas/list de pares); identidade interna de nó é
u32 via STRING INTERNING (page path ↔ page_id) — strings nunca são a
identidade das arestas dentro do kernel.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class BackendInfo:
    name: str                    # "python" | "rust"
    version: str                 # versão do pacote/extensão
    build: str = ""              # sha/feature flags do build nativo
    fallback_reason: str = ""    # por que NÃO é o backend pedido ("" = é)


@dataclass(frozen=True, slots=True)
class GraphHandle:
    """Snapshot IMUTÁVEL de grafo com interning. `native` carrega a
    representação do backend (CSR Rust ou dicts Python) — opaca para
    quem consome; `pages` é a string table id→path."""
    backend: str
    generation: str              # (bundle_head, index_generation) do load
    nodes: int
    edges: int
    pages: tuple[str, ...] = field(repr=False, default=())
    native: object = field(repr=False, default=None)


class ComputeKernel(Protocol):
    """Contrato do compute plane. Backends devolvem SINAIS (rankings,
    métricas, sketches, candidatos); a decisão semântica fica nos use
    cases. Métodos de lote recebem sequências e devolvem estruturas
    colunares simples — nunca list[dict] gigante."""

    def backend_info(self) -> BackendInfo: ...

    def load_graph(self, *, index_path: str,
                   connection=None) -> GraphHandle: ...

    def personalized_pagerank(
            self, graph: GraphHandle,
            seeds: dict[str, float], *,
            damping: float = 0.5, iterations: int = 20,
            tolerance: float = 1e-6,
            top_k: int = 12) -> list[tuple[str, float]]: ...

    def betweenness(self, graph: GraphHandle, *,
                    top_k: int = 0) -> dict[str, float]: ...

    def components(self, graph: GraphHandle) -> list[int]: ...

    def simhash_batch(self, texts: Sequence[str], *,
                      shingle: int = 3) -> list[int]: ...

    def consolidation_candidates(
            self, sketches: Sequence[int], *,
            max_hamming: int = 8) -> list[tuple[int, int]]: ...
