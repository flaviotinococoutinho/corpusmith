"""Observatório (Fase 5, v0.15) — consultas PURAS que alimentam os
indicadores do Cockpit: grafo navegável, gaps, topologia, atividade,
tracing de consultas e classificadores. Nada aqui escreve; tudo é
recomputável a partir de bundle + index.db + runtime.db.
"""
from __future__ import annotations
import json
from collections import defaultdict
from ..kernel.information import shannon_entropy
from ..kernel.topology import (betweenness_centrality, fragile_bridges,
                               structural_gaps as _structural_gaps)
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..settings import Settings

EDGE_WEIGHT = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}


def _pages_meta(settings: Settings) -> list[dict]:
    reader = BundleReader(settings.path("knowledge") / "bundle")
    out = []
    for d in reader.iter_concepts():
        x = d.meta.model_dump(exclude_none=True, mode="json")
        out.append({"page": d.rel_path, "type": d.meta.type,
                    "title": d.meta.title or d.rel_path,
                    "tags": d.meta.tags,
                    "privacy": x.get("privacy"),
                    "origin": str(x.get("generated_via", "")),
                    "confidence": x.get("confidence"),
                    "stale": bool(x.get("stale_as_of")),
                    "recycled": x.get("recycled", 0)})
    return out


# ------------------------------------------------------------------- grafo
def graph_data(settings: Settings) -> dict:
    """Nós + arestas + pontes para o grafo visual (estilo Obsidian)."""
    pages = _pages_meta(settings)
    idx = connect(settings.app_support / "index.db")
    edges = [{"src": r["src"], "dst": r["dst"],
              "confidence": r["confidence"] or "extracted"}
             for r in idx.execute(
                 "SELECT src, dst, COALESCE(confidence,'extracted') "
                 "confidence FROM graph_edges")]
    community = {r["page"]: r["community"] for r in
                 idx.execute("SELECT page, community FROM communities")}
    bridges = {(r["src"], r["dst"]) for r in
               idx.execute("SELECT src, dst FROM graph_bridges")}
    idx.close()
    rt = connect(settings.app_support / "runtime.db")
    heat = {r["path"]: r["score"] for r in
            rt.execute("SELECT path, score FROM page_heat")}
    rt.close()
    degree: dict[str, int] = defaultdict(int)
    linked: set[str] = set()
    for e in edges:
        degree[e["src"]] += 1
        degree[e["dst"]] += 1
        linked.add(e["dst"])
        e["bridge"] = (e["src"], e["dst"]) in bridges \
            or (e["dst"], e["src"]) in bridges
    # intermediação (v1.1): o "tamanho por influência" do grafo — quem
    # articula, calculado uma vez e reaproveitado pelas lacunas
    weighted = [(e["src"], e["dst"], EDGE_WEIGHT.get(e["confidence"], 0.5))
                for e in edges]
    betweenness = betweenness_centrality(weighted)
    nodes = [{**p, "degree": degree.get(p["page"], 0),
              "heat": round(heat.get(p["page"], 0.0), 3),
              "betweenness": betweenness.get(p["page"], 0.0),
              "community": community.get(p["page"], -1),
              "orphan": p["page"] not in linked}
             for p in pages]
    return {"nodes": nodes, "edges": edges}


# ------------------------------------------ lacunas estruturais (v1.1)
def structural_gaps(settings: Settings, limit: int = 8) -> dict:
    """Fios AUSENTES do discurso (solução própria inspirada no
    InfraNodus): blocos que quase nunca se conectam, com a pergunta-ponte
    determinística e os articuladores de cada lado."""
    graph = graph_data(settings)
    titles = {n["page"]: n["title"] for n in graph["nodes"]}
    betweenness = {n["page"]: n["betweenness"] for n in graph["nodes"]}
    community_of = {n["page"]: n["community"] for n in graph["nodes"]
                    if n["community"] >= 0}
    weighted = [(e["src"], e["dst"], EDGE_WEIGHT.get(e["confidence"], 0.5))
                for e in graph["edges"]]
    gaps = _structural_gaps(weighted, community_of, betweenness, limit=limit)
    out = []
    for g in gaps:
        ta = titles.get(g.rep_a, g.rep_a)
        tb = titles.get(g.rep_b, g.rep_b)
        out.append({
            "community_a": g.community_a, "community_b": g.community_b,
            "rep_a": g.rep_a, "rep_b": g.rep_b, "title_a": ta, "title_b": tb,
            "deficit": g.deficit, "expected": g.expected, "actual": g.actual,
            "question": f"Como {ta} se relaciona com {tb}?"})
    articulators = sorted(
        ({"page": n["page"], "title": n["title"],
          "betweenness": n["betweenness"]}
         for n in graph["nodes"] if n["betweenness"] > 0),
        key=lambda a: -a["betweenness"])[:10]
    return {"gaps": out, "articulators": articulators,
            "communities": len({n["community"] for n in graph["nodes"]
                                if n["community"] >= 0})}


# --------------------------------------------------------------- topologia
def _components(edges: list[dict], nodes: set[str]) -> list[int]:
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        a, b = e["src"], e["dst"]
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        parent[find(a)] = find(b)
    sizes: dict[str, int] = defaultdict(int)
    for n in parent:
        sizes[find(n)] += 1
    return sorted(sizes.values(), reverse=True)


# ----------------------------------------------------------------- insights
def insights(settings: Settings) -> dict:
    pages = _pages_meta(settings)
    graph = graph_data(settings)
    idx = connect(settings.app_support / "index.db")
    contested = [r["page"] for r in idx.execute(
        "SELECT page FROM page_overlay WHERE status='contested'")]
    bridge_rows = [dict(r) for r in idx.execute(
        "SELECT src, dst, weight FROM graph_bridges ORDER BY weight LIMIT 5")]
    idx.close()
    rt = connect(settings.app_support / "runtime.db")
    eval_rows = [dict(r) for r in rt.execute(
        "SELECT category, total, passed FROM eval_runs e WHERE ts = "
        "(SELECT MAX(ts) FROM eval_runs WHERE category = e.category) "
        "GROUP BY category")]
    events_day = [dict(r) for r in rt.execute(
        "SELECT date(created_at,'unixepoch') day, COUNT(*) n FROM events "
        "WHERE created_at > unixepoch() - 14*86400 GROUP BY day ORDER BY day")]
    top_events = [dict(r) for r in rt.execute(
        "SELECT type, COUNT(*) n FROM events "
        "WHERE created_at > unixepoch() - 14*86400 "
        "GROUP BY type ORDER BY n DESC LIMIT 10")]
    cold_count = 0
    try:
        cold = connect(settings.app_support / "cold.db")
        cold_count = cold.execute(
            "SELECT COUNT(*) c FROM cold_memories").fetchone()["c"]
        cold.close()
    except Exception:
        pass
    rt.close()

    def count_by(key: str) -> list:
        acc: dict[str, int] = defaultdict(int)
        for p in pages:
            acc[str(p.get(key) or "—")] += 1
        return sorted(acc.items(), key=lambda kv: -kv[1])

    node_names = {p["page"] for p in pages}
    components = _components(graph["edges"], node_names) or [0]
    degrees = [n["degree"] for n in graph["nodes"]] or [0]
    largest_pct = round(100 * components[0] / max(1, len(node_names)))
    # estrutura do discurso (v1.1, InfraNodus): evenness das comunidades
    # (entropia normalizada dos tamanhos) × conectividade (maior comp.)
    community_sizes: dict[int, int] = defaultdict(int)
    for n in graph["nodes"]:
        if n["community"] >= 0:
            community_sizes[n["community"]] += 1
    evenness = shannon_entropy(list(community_sizes.values()))
    connectedness = largest_pct / 100.0
    if len(node_names) < 3 or not community_sizes:
        structure = "incipiente"
    elif connectedness < 0.6:
        structure = "disperso"        # nenhum componente domina: ilhas
    elif evenness < 0.5:
        structure = "focado"          # um ou dois temas dominam
    else:
        structure = "diverso"         # vários temas equilibrados e ligados
    return {
        "gaps": {
            "questions": [p["page"] for p in pages if p["type"] == "question"],
            "orphans": [n["page"] for n in graph["nodes"] if n["orphan"]][:20],
            "contested": contested,
            "stale": [p["page"] for p in pages if p["stale"]][:20],
            "cold_count": cold_count,
            "eval": eval_rows,
        },
        "topology": {
            "nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
            "components": len(components),
            "largest_component_pct": largest_pct,
            "avg_degree": round(sum(degrees) / max(1, len(degrees)), 2),
            "bridges": bridge_rows,
            "communities": len(community_sizes),
            "structure": structure,
            "evenness": round(evenness, 3),
        },
        "activity": {"events_per_day": events_day,
                     "top_events": top_events},
        "classifiers": {
            "by_type": count_by("type"),
            "by_privacy": count_by("privacy"),
            "by_origin": count_by("origin"),
            "by_confidence": count_by("confidence"),
        },
    }


# ---------------------------------------------------------------- dicionário
def dictionary(settings: Settings) -> dict:
    """Os enums vivos do domínio: tipos, origens, confiança, vereditos,
    autoridades — cada um com o uso observado no bundle."""
    from ..harness.local_policy import RECOMMENDED_TYPES
    from ..okf.authorities import load_gazetteer
    pages = _pages_meta(settings)
    observed_types: dict[str, int] = defaultdict(int)
    origins: dict[str, int] = defaultdict(int)
    for p in pages:
        observed_types[p["type"]] += 1
        if p["origin"]:
            origins[p["origin"]] += 1
    gaz = load_gazetteer(BundleReader(settings.path("knowledge") / "bundle"))
    authorities: dict[str, int] = defaultdict(int)
    for _canonical, kind, _qid in set(gaz.map.values()):
        authorities[kind] += 1
    return {
        "types": sorted(
            [{"type": t, "recommended": t in RECOMMENDED_TYPES,
              "uses": observed_types.get(t, 0)}
             for t in sorted(RECOMMENDED_TYPES | set(observed_types))],
            key=lambda x: -x["uses"]),
        "origins": sorted(origins.items(), key=lambda kv: -kv[1]),
        "origin_prefixes": ["human:", "local:", "api:"],
        "confidence_scale": ["extracted", "inferred", "ambiguous"],
        "verdicts": ["useful", "dead_end", "corrected"],
        "privacy_values": ["local_only", "api_allowed"],
        "log_kinds": ["Creation", "Update", "Deprecation", "Review",
                      "Freeze", "Recall"],
        "authorities": sorted(authorities.items(), key=lambda kv: -kv[1]),
        "gazetteer_terms": len(set(gaz.map.values())),
    }


# ------------------------------------------------------------------ tracing
def traces(settings: Settings, limit: int = 20) -> list[dict]:
    rt = connect(settings.app_support / "runtime.db")
    rows = [dict(r) for r in rt.execute(
        "SELECT p.ask_id, COUNT(DISTINCT p.page) pages, "
        "GROUP_CONCAT(DISTINCT p.stream) streams, "
        "MAX(o.verdict) verdict "
        "FROM ask_provenance p LEFT JOIN ask_outcomes o "
        "ON o.ask_id = p.ask_id "
        "GROUP BY p.ask_id ORDER BY p.rowid DESC LIMIT ?", (limit,))]
    rt.close()
    return rows


def trace(settings: Settings, ask_id: str) -> dict:
    rt = connect(settings.app_support / "runtime.db")
    rows = [dict(r) for r in rt.execute(
        "SELECT page, stream FROM ask_provenance WHERE ask_id=?", (ask_id,))]
    outcome = rt.execute(
        "SELECT verdict, note, pages FROM ask_outcomes WHERE ask_id=? "
        "ORDER BY id DESC LIMIT 1", (ask_id,)).fetchone()
    weights = {r["stream"]: r["weight"] for r in
               rt.execute("SELECT stream, weight FROM stream_weights")}
    rt.close()
    by_page: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_page[r["page"]].append(r["stream"])
    return {"ask_id": ask_id,
            "pages": [{"page": p, "streams": sorted(s)}
                      for p, s in by_page.items()],
            "outcome": ({"verdict": outcome["verdict"],
                         "note": outcome["note"],
                         "pages": json.loads(outcome["pages"] or "[]")}
                        if outcome else None),
            "stream_weights": weights}
