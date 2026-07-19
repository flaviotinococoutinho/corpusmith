"""Cache de grafo por GERAÇÃO (ADR-39 §12): o /ask não reconstrói o
grafo a cada pergunta. Chave = (bundle_head:index_generation, backend);
snapshot IMUTÁVEL; swap atômico por troca de referência; invalidação é
a própria mudança de geração (comparada a cada acesso — barata: uma
consulta a index_meta). Métricas hit/miss/build expostas em
graph_cache_stats() (bench e /cockpit consomem).
"""
from __future__ import annotations
import threading
from .types import GraphHandle

_LOCK = threading.Lock()
# backend → (geração DO CHAMADOR na hora do build, snapshot)
_CACHE: dict[str, tuple[str, GraphHandle]] = {}
_STATS = {"hits": 0, "misses": 0, "builds": 0, "invalidations": 0}


def cached_graph(kernel, *, index_path: str, connection=None,
                 generation: str) -> GraphHandle:
    """Devolve o snapshot da geração vigente; reconstrói só quando a
    geração (chave do CHAMADOR) muda ou no primeiro acesso. Erro no
    build propaga — quem chama decide o fallback."""
    backend = kernel.backend_info().name
    with _LOCK:
        held = _CACHE.get(backend)
        if held is not None and held[0] == generation:
            _STATS["hits"] += 1
            return held[1]
        _STATS["misses"] += 1
        if held is not None:
            _STATS["invalidations"] += 1
    built = kernel.load_graph(index_path=index_path, connection=connection)
    with _LOCK:
        _STATS["builds"] += 1
        _CACHE[backend] = (generation, built)   # swap atômico da referência
    return built


def graph_cache_stats() -> dict:
    with _LOCK:
        entries = {b: {"generation": key, "nodes": g.nodes,
                       "edges": g.edges}
                   for b, (key, g) in _CACHE.items()}
        return {**_STATS, "entries": entries}


def invalidate() -> None:
    """Invalidação explícita (testes/doctor)."""
    with _LOCK:
        _CACHE.clear()
        _STATS["invalidations"] += 1
