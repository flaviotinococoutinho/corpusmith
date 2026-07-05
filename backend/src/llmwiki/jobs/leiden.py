"""Job `leiden` (Parte V §7.4): comunidades do grafo de links.
Sem igraph/leidenalg instalados (extra [ml]), cai em componentes conexos —
suficiente para os overlays do cockpit."""
from __future__ import annotations
from collections import defaultdict
from ..runtime.db import connect
from ..settings import Settings


def _components(edges: list[tuple[str, str]]) -> dict[str, int]:
    adj: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    comm: dict[str, int] = {}
    cid = 0
    for start in adj:
        if start in comm:
            continue
        stack = [start]
        while stack:
            n = stack.pop()
            if n in comm:
                continue
            comm[n] = cid
            stack.extend(adj[n] - comm.keys())
        cid += 1
    return comm


def run(s: Settings, payload: dict, emit) -> dict:
    idx = connect(s.app_support / "index.db")
    edges = [(r["src"], r["dst"]) for r in
             idx.execute("SELECT src,dst FROM graph_edges")]
    try:
        import igraph, leidenalg                      # noqa: F401  extra [ml]
        g = igraph.Graph.TupleList(edges)
        part = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition)
        comm = {g.vs[v]["name"]: i for i, c in enumerate(part) for v in c}
    except ImportError:
        comm = _components(edges)
    idx.execute("DELETE FROM communities")
    idx.executemany("INSERT INTO communities(page,community) VALUES (?,?)",
                    list(comm.items()))
    idx.commit()
    idx.close()
    return {"communities": len(set(comm.values())), "pages": len(comm)}
