"""F2-PR3+4 (ADR-44) — Brandes fora do request, pelo kernel que já existia.

O produto tinha data de morte, e o número está no `benchmarks/baseline.json`:
Brandes em Python custa **88 058 ms** a 5000 nós contra **1 944 ms** em Rust
(45×). Duas coisas somavam nisso, as duas medidas antes de escrever:

1. o cálculo acontecia **no request**. A 1200 páginas era 95% do custo de
   `graph_data` (2571 ms de 2571; a 100 páginas, 52%), crescendo ~O(n²);
2. o caminho quente **ignorava o `ComputeKernel`**. O kernel selecionava
   `rust` e o `observatory` chamava o `betweenness_centrality` puro em
   Python direto — a camada nativa estava paga e não estava sendo usada.

Depois: `graph_data` a 1200 páginas passa de **2571 ms para 139 ms** (18,5×) e
o Brandes vira trabalho do job `leiden`, semanal e prioridade baixa.

O teste mais importante deste arquivo não é o de tempo — é o que prova que os
valores persistidos são **idênticos** aos que o request calculava. Sem ele,
"ficou 18× mais rápido" poderia ser só "passou a responder outra coisa".
"""
from __future__ import annotations
import pytest
from llmwiki.kernel.topology import betweenness_centrality
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval import observatory
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import SCHEMA_VERSIONS, connect
from llmwiki.usecases.detect_communities import DetectCommunities

EDGE_WEIGHT = {"extracted": 1.0, "inferred": 0.5, "ambiguous": 0.15}


def _doc(rel, title, body):
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only",
                                           generated_via="human:promote"))


@pytest.fixture
def base(settings, kb):
    """Seis blocos em cadeia: os nós de fio único são os articuladores, então
    a intermediação tem valores DISTINTOS de zero para comparar."""
    docs = []
    for b in range(6):
        for i in range(5):
            viz = "\n".join(f"- [b{b} p{j}](/concepts/b{b}-p{j}.md)"
                            for j in range(5) if j != i)
            fio = (f"\n- [b{b+1} p0](/concepts/b{b+1}-p0.md)"
                   if i == 0 and b + 1 < 6 else "")
            docs.append(_doc(f"concepts/b{b}-p{i}.md", f"b{b} p{i}",
                             f"# b{b} p{i}\n\n{viz}{fio}\n"))
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    return settings


def _do_request(settings) -> dict:
    return observatory.graph_data(settings)


# ================== a garantia que sustenta o ganho: MESMO resultado
def test_centralidade_persistida_e_identica_a_que_o_request_calculava(base):
    """O teste central. "18× mais rápido" só vale se for a MESMA resposta —
    senão é só ter passado a responder outra coisa.

    O kernel lê `graph_edges` da mesma conexão e aplica o MESMO `EDGE_WEIGHT`
    do `observatory`. Alimentá-lo com o `adjacency` do leiden seria tentador e
    estaria errado por duas razões: ele carrega arestas de co-menção que a
    centralidade nunca teve, e `load_edges` mapeia o terceiro campo por
    `EDGE_WEIGHT`, então peso já acumulado viraria 0.5 para tudo."""
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    persistida = {r["page"]: r["betweenness"]
                  for r in idx.execute("SELECT page, betweenness "
                                       "FROM graph_centrality")}
    arestas = [(r[0], r[1], EDGE_WEIGHT.get(r[2], 0.5)) for r in idx.execute(
        "SELECT src, dst, COALESCE(confidence,'extracted') FROM graph_edges")]
    idx.close()
    esperada = betweenness_centrality(arestas)
    assert persistida, "nada foi persistido"
    assert set(persistida) == set(esperada)
    for page, valor in esperada.items():
        assert abs(persistida[page] - valor) < 1e-6, page
    # e o cenário tem intermediação REAL — senão o teste passaria por vacuidade
    assert max(esperada.values()) > 0


def test_o_request_serve_o_valor_persistido(base):
    DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    persistida = {r["page"]: r["betweenness"]
                  for r in idx.execute("SELECT page, betweenness "
                                       "FROM graph_centrality")}
    idx.close()
    grafo = _do_request(base)
    for n in grafo["nodes"]:
        assert n["betweenness"] == pytest.approx(
            persistida.get(n["page"], 0.0)), n["page"]


def test_o_request_nao_calcula_mais_brandes(base, monkeypatch):
    """Guarda contra a regressão que devolveria a data de morte ao produto:
    alguém volta a chamar o kernel puro no caminho quente e a suíte, que roda
    em bundles pequenos, continuaria verde."""
    DetectCommunities(base).execute()
    import llmwiki.kernel.topology as topo
    chamou = []
    monkeypatch.setattr(topo, "betweenness_centrality",
                        lambda *a, **k: chamou.append(1) or {})
    _do_request(base)
    observatory.structural_gaps(base)
    assert not chamou, "o request voltou a calcular Brandes"


# ================== o que acontece quando a centralidade NÃO foi medida
def test_sem_centralidade_o_request_declara_e_serve_zero(base):
    """Mapa não computado é estado NORMAL de instalação nova. A interface
    serve GRAU em vez de inventar influência, e a chave nunca desaparece do
    payload — há teste de shape (D-J) que depende dela."""
    grafo = _do_request(base)
    assert grafo["centrality"]["computed"] is False
    assert grafo["centrality"]["backend"] == "none"
    assert all("betweenness" in n for n in grafo["nodes"])
    assert all(n["betweenness"] == 0.0 for n in grafo["nodes"])
    # e o grau continua informativo
    assert max(n["degree"] for n in grafo["nodes"]) > 0


def test_gaps_sem_centralidade_nao_quebra(base):
    """`structural_gaps` ranqueia articuladores por intermediação; com ela
    ausente a lista sai vazia, não com erro."""
    out = observatory.structural_gaps(base)
    assert out["articulators"] == []
    assert isinstance(out["gaps"], list)


def test_carimbo_declara_quem_mediu_a_centralidade(base):
    out = DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    snap = dict(idx.execute("SELECT * FROM graph_snapshot WHERE id=1"
                            ).fetchone())
    idx.close()
    assert snap["centrality_backend"] in ("python", "rust")
    assert snap["centrality_backend"] == out["centrality_backend"]
    grafo = _do_request(base)
    assert grafo["centrality"]["backend"] == snap["centrality_backend"]
    assert grafo["centrality"]["computed"] is True


def test_falha_do_kernel_nao_derruba_o_job(base, monkeypatch):
    """A centralidade é enfeite do mapa, não o mapa (ADR-39 §22: ausência de
    camada nativa é comportamento suportado). O job entrega comunidades e
    pontes, e declara `none`."""
    import llmwiki.compute as compute

    def explode(*a, **k):
        raise RuntimeError("kernel indisponível")

    monkeypatch.setattr(compute, "get_kernel", explode)
    out = DetectCommunities(base).execute()
    assert out["centrality_backend"] == "none"
    assert out["communities"] >= 1, "o mapa tem de sair mesmo assim"
    idx = connect(base.app_support / "index.db")
    assert idx.execute("SELECT COUNT(*) c FROM graph_centrality"
                       ).fetchone()["c"] == 0
    idx.close()
    assert _do_request(base)["centrality"]["computed"] is False


# ================== migração
def test_index_migra_de_v7_para_v8_sem_perder_o_carimbo(base):
    """`CREATE TABLE IF NOT EXISTS` NÃO acrescenta coluna a tabela existente:
    um `index.db` v7 já tem `graph_snapshot` sem `centrality_backend`, e sem o
    ALTER o carimbo falharia na PRIMEIRA escrita. Simulado dropando a coluna
    via recriação da tabela no formato v7."""
    assert SCHEMA_VERSIONS["index.db"] >= 8
    DetectCommunities(base).execute()
    caminho = base.app_support / "index.db"
    idx = connect(caminho)
    idx.executescript(
        "DROP TABLE graph_snapshot;"
        "CREATE TABLE graph_snapshot(id INTEGER PRIMARY KEY CHECK(id=1),"
        " bundle_head TEXT NOT NULL, computed_at REAL NOT NULL,"
        " backend TEXT NOT NULL, seed INTEGER, nodes INTEGER NOT NULL,"
        " edges INTEGER NOT NULL, communities INTEGER NOT NULL,"
        " bridges INTEGER NOT NULL, hubs_excluded INTEGER NOT NULL);")
    idx.commit()
    assert "centrality_backend" not in {
        r["name"] for r in idx.execute("PRAGMA table_info(graph_snapshot)")}
    idx.close()
    # reabrir dispara o _migrate; o job seguinte escreve sem falhar
    from llmwiki.runtime.db import _INITIALIZED
    _INITIALIZED.discard(str(caminho.resolve()))
    out = DetectCommunities(base).execute()
    assert out["centrality_backend"] in ("python", "rust", "none")
    idx = connect(caminho)
    assert "centrality_backend" in {
        r["name"] for r in idx.execute("PRAGMA table_info(graph_snapshot)")}
    idx.close()


# ================== o recorte do subgrafo
def test_limit_recorta_subgrafo_e_declara_o_total(base):
    """Recorte é do TRANSPORTE, não do cálculo: as contagens continuam
    falando do grafo inteiro, senão o limite viraria mentira sobre o tamanho
    da rede."""
    inteiro = _do_request(base)
    assert inteiro["truncated"] is False
    n = 7
    parcial = observatory.graph_data(base, limit=n)
    assert len(parcial["nodes"]) == n
    assert parcial["truncated"] is True
    assert parcial["total_nodes"] == inteiro["total_nodes"]
    assert parcial["total_edges"] == inteiro["total_edges"]
    # nenhuma aresta pendurada: só arestas entre nós visíveis
    visiveis = {x["page"] for x in parcial["nodes"]}
    assert all(e["src"] in visiveis and e["dst"] in visiveis
               for e in parcial["edges"])


def test_limit_e_deterministico(base):
    """Sem critério de desempate estável, o recorte muda entre execuções e o
    grafo "pisca" sem o conhecimento ter mudado."""
    a = [n["page"] for n in observatory.graph_data(base, limit=9)["nodes"]]
    for _ in range(3):
        assert [n["page"] for n in
                observatory.graph_data(base, limit=9)["nodes"]] == a


def test_limit_maior_que_o_grafo_nao_trunca(base):
    grafo = observatory.graph_data(base, limit=10_000)
    assert grafo["truncated"] is False
    assert len(grafo["nodes"]) == grafo["total_nodes"]
