"""Job `leiden` (Parte V §7.4 + v0.8 §7): comunidades do grafo de links
com PESOS por confiança (§1.4), arestas 'inferred' por co-menção de
entidade, exclusão de super-hubs (p99 de grau, graphify) e páginas
`community_summary` geradas (graphrag) — LLM LOCAL, com fallback
determinístico. Sem igraph/leidenalg (extra [ml]), cai em componentes
conexos ponderados."""
from __future__ import annotations
import hashlib
import itertools
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from ..models.router import ModelRouter, ModelUnavailable
from ..okf.authorities import load_gazetteer, normalize_machine_body
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.writer import BundleWriter
from ..runtime.db import connect
from ..settings import Settings

W = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}


def _slug(name: str) -> str:
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "comunidade"


def _components(adj: dict[str, dict[str, float]]) -> dict[str, int]:
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
            stack.extend(x for x in adj[n] if x not in comm)
        cid += 1
    return comm


def run(s: Settings, payload: dict, emit) -> dict:
    idx = connect(s.app_support / "index.db")

    # (a) grafo ponderado por confiança
    adj: dict[str, dict[str, float]] = defaultdict(dict)

    def add_edge(a: str, b: str, w: float) -> None:
        if a == b:
            return
        adj[a][b] = adj[a].get(b, 0.0) + w
        adj[b][a] = adj[b].get(a, 0.0) + w

    for src, dst, conf in idx.execute(
            "SELECT src, dst, COALESCE(confidence,'extracted') FROM graph_edges"):
        add_edge(src, dst, W.get(conf, 0.5))

    # (b) arestas 'inferred' por co-menção de entidade (teto anti-hub na origem)
    for (eid,) in idx.execute(
            "SELECT entity_id FROM page_entities GROUP BY entity_id "
            "HAVING COUNT(DISTINCT page) BETWEEN 2 AND 30"):
        pages = [r[0] for r in idx.execute(
            "SELECT DISTINCT page FROM page_entities WHERE entity_id=?", (eid,))]
        for a, b in itertools.combinations(pages, 2):
            add_edge(a, b, W["inferred"] * 0.5)

    # (c) exclusão de super-hubs (p99 de grau) antes do particionamento
    degs = sorted(len(nb) for nb in adj.values())
    hubs: set[str] = set()
    if degs:
        p99 = degs[int(0.99 * (len(degs) - 1))]
        hubs = {n for n, nb in adj.items() if len(nb) > max(p99, 8)}
    core = {n: {m: w for m, w in nb.items() if m not in hubs}
            for n, nb in adj.items() if n not in hubs}
    try:
        import igraph, leidenalg                       # noqa: F401  extra [ml]
        edges, weights = [], []
        for a in core:
            for b, w in core[a].items():
                if a < b:
                    edges.append((a, b))
                    weights.append(w)
        g = igraph.Graph.TupleList(edges)
        part = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition,
                                        weights=weights)
        comm = {g.vs[v]["name"]: i for i, c in enumerate(part) for v in c}
    except ImportError:
        comm = _components(core)
    for h in hubs:                                     # atribuição pós-hoc
        nb = [comm.get(x) for x in adj[h] if comm.get(x) is not None]
        comm[h] = max(set(nb), key=nb.count) if nb else -1

    idx.execute("DELETE FROM communities")
    idx.executemany("INSERT INTO communities(page,community) VALUES (?,?)",
                    list(comm.items()))
    idx.commit()

    # (d) rótulo + sumário de comunidade → páginas community_summary
    members_by_c: dict[int, list[str]] = defaultdict(list)
    for page, cid in comm.items():
        if cid >= 0 and not page.startswith("communities/"):
            members_by_c[cid].append(page)
    kb = s.path("knowledge")
    writer = BundleWriter(kb)
    gaz = load_gazetteer(writer.reader)
    router = ModelRouter(s)
    written = 0
    for cid, members in members_by_c.items():
        if len(members) < 2:
            continue
        # centralidade barata: grau ponderado dentro da comunidade
        top = sorted(members,
                     key=lambda p: -sum(adj[p].values()) if p in adj else 0)[:8]
        titles = [(p, p.rsplit("/", 1)[-1][:-3].replace("-", " ")) for p in top]
        label, resumo = titles[0][1], "Tema comum: " + ", ".join(
            t for _, t in titles[:4]) + "."
        try:
            r = router.complete(
                "Nomeie em 2-4 palavras e resuma em 3 frases o tema comum "
                "destas páginas (responda 'ROTULO: ...\nRESUMO: ...'):\n"
                + "\n".join(f"- {t}" for _, t in titles),
                privacy="local_only", max_tokens=160)
            m = re.search(r"ROTULO:\s*(.+)", r["text"])
            mr = re.search(r"RESUMO:\s*(.+)", r["text"], re.S)
            if m:
                label = m.group(1).strip()[:60]
            if mr:
                resumo = mr.group(1).strip()[:800]
        except (ModelUnavailable, Exception):
            pass
        body, rep = normalize_machine_body(
            f"# {label}\n\n{resumo}\n\n## Membros centrais\n"
            + "\n".join(f"- [{t}](/{p})" for p, t in titles) + "\n", gaz)
        doc = OKFDocument(
            rel_path=f"communities/{_slug(label)}.md",
            body=body,
            meta=OKFFrontMatter(
                type="community_summary", title=label,
                description=resumo[:200],
                timestamp=datetime.now(timezone.utc),
                entities=rep.entities_frontmatter() or None,
                **{"privacy": "local_only",
                   "generated_via": "local:leiden",
                   "source_sha256": hashlib.sha256(
                       "\n".join(sorted(members)).encode()).hexdigest()}))
        writer.write([doc], log_kind="Update",
                     log_message=f"comunidade {cid}: {label}",
                     commit_message=f"leiden: {_slug(label)}")
        written += 1
    idx.close()
    return {"communities": len(members_by_c), "pages": len(comm),
            "hubs_excluded": len(hubs), "summaries": written}
