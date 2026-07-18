"""v1.1 — leitura de rede de texto (InfraNodus próprio): intermediação de
Brandes, lacunas estruturais pelo modelo de configuração e estrutura do
discurso. Kernel puro por propriedade + observatório via API."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.kernel.topology import (betweenness_centrality, structural_gaps)
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": "t"})
        yield c


# --------------------------------------------------------- intermediação
def test_betweenness_star_center_is_maximal():
    star = [("s", f"leaf{i}", 1.0) for i in range(4)]
    bet = betweenness_centrality(star)
    assert bet["s"] == 1.0                       # todo caminho passa no centro
    assert all(bet[f"leaf{i}"] == 0.0 for i in range(4))


def test_betweenness_path_peaks_in_the_middle():
    path = [("a", "b", 1.0), ("b", "c", 1.0), ("c", "d", 1.0),
            ("d", "e", 1.0)]
    bet = betweenness_centrality(path)
    assert bet["c"] > bet["b"] == bet["d"] > bet["a"] == bet["e"] == 0.0


def test_betweenness_ignores_direct_triangle():
    triangle = [("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0)]
    assert all(v == 0.0 for v in betweenness_centrality(triangle).values())


# --------------------------------------------------------- lacuna estrutural
def _triangle(prefix):
    return [(f"{prefix}a", f"{prefix}b", 1.0),
            (f"{prefix}b", f"{prefix}c", 1.0),
            (f"{prefix}a", f"{prefix}c", 1.0)]


def test_disconnected_clusters_are_a_gap():
    edges = _triangle("x/") + _triangle("y/")
    community = {"x/a": 0, "x/b": 0, "x/c": 0,
                 "y/a": 1, "y/b": 1, "y/c": 1}
    bet = betweenness_centrality(edges)
    gaps = structural_gaps(edges, community, bet)
    assert len(gaps) == 1
    gap = gaps[0]
    assert {gap.community_a, gap.community_b} == {0, 1}
    assert gap.actual == 0 and gap.deficit > 0     # fio ausente
    assert gap.expected > 0


def test_gap_actual_preserva_peso_fracionario():
    """Fio FRACO ≠ fio AUSENTE (a distinção central do produto): `actual`
    carrega o peso fracionário real — arestas `inferred` pesam 0.5 e
    truncar para int chamava de "ausente" uma ligação que existe."""
    edges = _triangle("x/") + _triangle("y/") + [("x/a", "y/a", 0.5)]
    community = {"x/a": 0, "x/b": 0, "x/c": 0,
                 "y/a": 1, "y/b": 1, "y/c": 1}
    gaps = structural_gaps(edges, community, betweenness_centrality(edges))
    assert len(gaps) == 1
    assert gaps[0].actual == pytest.approx(0.5)    # fio fraco, não ausente
    assert gaps[0].deficit == pytest.approx(gaps[0].expected - 0.5, abs=1e-3)


def test_well_connected_pair_is_not_a_gap():
    # ligadas ACIMA do esperado pelo acaso (bipartido completo) ⇒ sem lacuna
    edges = [("0/a", "1/c", 1.0), ("0/a", "1/d", 1.0),
             ("0/b", "1/c", 1.0), ("0/b", "1/d", 1.0)]
    community = {"0/a": 0, "0/b": 0, "1/c": 1, "1/d": 1}
    gaps = structural_gaps(edges, community, betweenness_centrality(edges))
    assert gaps == []                              # déficit ≤ 0


def test_gap_representative_is_the_articulator():
    # cluster 0: caminho a-b-c (b articula); cluster 1: d-e-f (e articula)
    edges = [("0/a", "0/b", 1.0), ("0/b", "0/c", 1.0),
             ("1/d", "1/e", 1.0), ("1/e", "1/f", 1.0)]
    community = {"0/a": 0, "0/b": 0, "0/c": 0,
                 "1/d": 1, "1/e": 1, "1/f": 1}
    gaps = structural_gaps(edges, community, betweenness_centrality(edges))
    assert gaps and gaps[0].rep_a == "0/b" and gaps[0].rep_b == "1/e"


# ------------------------------------------------------- observatório / API
def _doc(rel, title, body):
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only"))


def _two_clusters(settings, kb):
    docs = [
        _doc("concepts/rest.md", "REST",
             "# REST\n\nver [HTTP](/concepts/http.md) e "
             "[JSON](/concepts/json.md)."),
        _doc("concepts/http.md", "HTTP",
             "# HTTP\n\nver [REST](/concepts/rest.md) e "
             "[JSON](/concepts/json.md)."),
        _doc("concepts/json.md", "JSON",
             "# JSON\n\nver [REST](/concepts/rest.md)."),
        _doc("concepts/glp1.md", "GLP-1",
             "# GLP-1\n\nver [insulina](/concepts/insulina.md) e "
             "[metabolismo](/concepts/metabolismo.md)."),
        _doc("concepts/insulina.md", "Insulina",
             "# Insulina\n\nver [GLP-1](/concepts/glp1.md) e "
             "[metabolismo](/concepts/metabolismo.md)."),
        _doc("concepts/metabolismo.md", "Metabolismo",
             "# Metabolismo\n\nver [insulina](/concepts/insulina.md)."),
    ]
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    # comunidades (o leiden faria isto; aqui fixamos para testar a leitura)
    idx = connect(settings.app_support / "index.db")
    for page in ("concepts/rest.md", "concepts/http.md", "concepts/json.md"):
        idx.execute("INSERT INTO communities(page, community) VALUES (?,0)",
                    (page,))
    for page in ("concepts/glp1.md", "concepts/insulina.md",
                 "concepts/metabolismo.md"):
        idx.execute("INSERT INTO communities(page, community) VALUES (?,1)",
                    (page,))
    idx.commit()
    idx.close()


def test_gaps_endpoint_finds_the_disconnected_theme(client, settings, kb):
    _two_clusters(settings, kb)
    body = client.get("/cockpit/gaps").json()
    assert len(body["gaps"]) == 1
    gap = body["gaps"][0]
    assert {gap["title_a"], gap["title_b"]} & {"REST", "HTTP", "JSON"}
    assert {gap["title_a"], gap["title_b"]} & {"GLP-1", "Insulina",
                                               "Metabolismo"}
    assert gap["actual"] == 0 and gap["deficit"] > 0
    assert "se relaciona com" in gap["question"]   # pergunta-ponte
    assert isinstance(body["articulators"], list)  # vazio em clusters densos


def test_insights_reports_discourse_structure(client, settings, kb):
    _two_clusters(settings, kb)
    topo = client.get("/cockpit/insights").json()["topology"]
    assert topo["communities"] == 2
    assert topo["structure"] == "disperso"         # 2 blocos sem ligação
    assert "evenness" in topo


def test_graph_nodes_carry_betweenness(client, settings, kb):
    _two_clusters(settings, kb)
    nodes = client.get("/cockpit/graph").json()["nodes"]
    assert all("betweenness" in n for n in nodes)
