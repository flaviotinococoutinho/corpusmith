"""DetectCommunities (v0.8 §7 como use case, v0.9 + topologia).

Além das comunidades (Leiden ou componentes ponderados) e das páginas
community_summary (via o MESMO Template Method de página de máquina),
computa as PONTES FRÁGEIS do grafo por persistência 0-dimensional
(kernel.topology): pares de blocos de conhecimento unidos por um único fio
fraco — o diagnóstico topológico que a curadoria usa para linkar temas.
"""
from __future__ import annotations
import hashlib
import itertools
import re
import unicodedata
from collections import defaultdict
from .base import DraftPage, MachinePageUseCase, UseCase
from ..kernel.topology import fragile_bridges
from ..models.router import ModelRouter, ModelUnavailable
from ..runtime.db import connect
from ..settings import Settings

W = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}


def _slug(name: str) -> str:
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "comunidade"


class _CommunitySummaryPage(MachinePageUseCase):
    LOG_KIND = "Update"

    def __init__(self, settings: Settings, label: str, summary: str,
                 members: list[tuple[str, str]], fingerprint: str):
        super().__init__(settings)
        self._label = label
        self._summary = summary
        self._members = members
        self._fingerprint = fingerprint

    def _produce(self) -> DraftPage:
        body = (f"# {self._label}\n\n{self._summary}\n\n## Membros centrais\n"
                + "\n".join(f"- [{title}](/{page})"
                            for page, title in self._members) + "\n")
        return DraftPage(
            rel_path=f"communities/{_slug(self._label)}.md",
            title=self._label, body=body,
            meta={"type": "community_summary",
                  "description": self._summary[:200],
                  "privacy": "local_only",
                  "generated_via": "local:leiden",
                  "source_sha256": self._fingerprint},
            log_message=f"comunidade: {self._label}",
            commit_message=f"leiden: {_slug(self._label)}")


class DetectCommunities(UseCase):
    def __init__(self, settings: Settings, notify=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)
        self._router = ModelRouter(settings)

    def execute(self) -> dict:
        idx = connect(self._settings.app_support / "index.db")
        adjacency = self._weighted_graph(idx)
        self._store_bridges(idx, adjacency)
        communities = self._partition(adjacency)
        idx.execute("DELETE FROM communities")
        idx.executemany("INSERT INTO communities(page,community) VALUES (?,?)",
                        list(communities.items()))
        idx.commit()
        summaries = self._write_summaries(adjacency, communities)
        idx.close()
        distinct = {c for c in communities.values() if c >= 0}
        return {"communities": len(distinct), "pages": len(communities),
                "summaries": summaries}

    # -------------------------------------------------------------- grafo
    def _weighted_graph(self, idx) -> dict[str, dict[str, float]]:
        adjacency: dict[str, dict[str, float]] = defaultdict(dict)

        def add_edge(a: str, b: str, weight: float) -> None:
            if a == b:
                return
            adjacency[a][b] = adjacency[a].get(b, 0.0) + weight
            adjacency[b][a] = adjacency[b].get(a, 0.0) + weight

        for src, dst, conf in idx.execute(
                "SELECT src, dst, COALESCE(confidence,'extracted') "
                "FROM graph_edges"):
            add_edge(src, dst, W.get(conf, 0.5))
        # arestas inferred por co-menção de entidade (teto anti-hub na origem)
        for (eid,) in idx.execute(
                "SELECT entity_id FROM page_entities GROUP BY entity_id "
                "HAVING COUNT(DISTINCT page) BETWEEN 2 AND 30"):
            pages = [r[0] for r in idx.execute(
                "SELECT DISTINCT page FROM page_entities WHERE entity_id=?",
                (eid,))]
            for a, b in itertools.combinations(pages, 2):
                add_edge(a, b, W["inferred"] * 0.5)
        return adjacency

    def _store_bridges(self, idx, adjacency) -> None:
        """Persistência 0-dim: as pontes mais frágeis entre blocos reais."""
        edges = [(a, b, w) for a, neighbors in adjacency.items()
                 for b, w in neighbors.items() if a < b]
        idx.execute("DELETE FROM graph_bridges")
        for event in fragile_bridges(edges, limit=10):
            idx.execute(
                "INSERT OR REPLACE INTO graph_bridges VALUES (?,?,?,?,?)",
                (event.src, event.dst, event.weight,
                 event.small_side, event.large_side))
        idx.commit()

    def _partition(self, adjacency) -> dict[str, int]:
        # exclusão de super-hubs (p99 de grau) antes do particionamento
        degrees = sorted(len(nb) for nb in adjacency.values())
        hubs: set[str] = set()
        if degrees:
            p99 = degrees[int(0.99 * (len(degrees) - 1))]
            hubs = {n for n, nb in adjacency.items() if len(nb) > max(p99, 8)}
        core = {n: {m: w for m, w in nb.items() if m not in hubs}
                for n, nb in adjacency.items() if n not in hubs}
        communities = self._leiden_or_components(core)
        for hub in hubs:                               # atribuição pós-hoc
            neighborhood = [communities.get(x) for x in adjacency[hub]
                            if communities.get(x) is not None]
            communities[hub] = (max(set(neighborhood), key=neighborhood.count)
                                if neighborhood else -1)
        return communities

    @staticmethod
    def _leiden_or_components(core) -> dict[str, int]:
        try:
            import igraph, leidenalg                   # noqa: F401  extra [ml]
            edges, weights = [], []
            for a in core:
                for b, w in core[a].items():
                    if a < b:
                        edges.append((a, b))
                        weights.append(w)
            g = igraph.Graph.TupleList(edges)
            part = leidenalg.find_partition(
                g, leidenalg.ModularityVertexPartition, weights=weights)
            return {g.vs[v]["name"]: i for i, c in enumerate(part) for v in c}
        except ImportError:
            communities: dict[str, int] = {}
            next_id = 0
            for start in core:
                if start in communities:
                    continue
                stack = [start]
                while stack:
                    node = stack.pop()
                    if node in communities:
                        continue
                    communities[node] = next_id
                    stack.extend(x for x in core[node]
                                 if x not in communities)
                next_id += 1
            return communities

    # ----------------------------------------------------------- sumários
    def _write_summaries(self, adjacency, communities) -> int:
        members_by_community: dict[int, list[str]] = defaultdict(list)
        for page, community in communities.items():
            if community >= 0 and not page.startswith("communities/"):
                members_by_community[community].append(page)
        written = 0
        for community, members in members_by_community.items():
            if len(members) < 2:
                continue
            top = sorted(members, key=lambda p: -sum(
                adjacency[p].values()) if p in adjacency else 0)[:8]
            titles = [(p, p.rsplit("/", 1)[-1][:-3].replace("-", " "))
                      for p in top]
            label, summary = self._label(titles)
            fingerprint = hashlib.sha256(
                "\n".join(sorted(members)).encode()).hexdigest()
            _CommunitySummaryPage(self._settings, label, summary,
                                  titles, fingerprint).execute()
            written += 1
        return written

    def _label(self, titles: list[tuple[str, str]]) -> tuple[str, str]:
        label = titles[0][1]
        summary = "Tema comum: " + ", ".join(t for _, t in titles[:4]) + "."
        try:
            r = self._router.complete(
                "Nomeie em 2-4 palavras e resuma em 3 frases o tema comum "
                "destas páginas (responda 'ROTULO: ...\nRESUMO: ...'):\n"
                + "\n".join(f"- {t}" for _, t in titles),
                privacy="local_only", max_tokens=160)
            found = re.search(r"ROTULO:\s*(.+)", r["text"])
            found_summary = re.search(r"RESUMO:\s*(.+)", r["text"], re.S)
            if found:
                label = found.group(1).strip()[:60]
            if found_summary:
                summary = found_summary.group(1).strip()[:800]
        except (ModelUnavailable, Exception):
            pass
        return label, summary
