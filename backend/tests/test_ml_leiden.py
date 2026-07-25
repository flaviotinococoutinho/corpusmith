"""PR-0 (G-2) — o ramo de particionamento de PRODUÇÃO passa a ser exercitado.

`DetectCommunities._leiden_or_components` tem dois ramos: Leiden real
(`igraph`/`leidenalg`, extra `[ml]`) e um fallback de componentes conexos.
Até aqui a CI instalava só `[dev]`, então **o ramo que roda em produção
nunca era executado por teste** — toda a cobertura de comunidades vinha do
fallback. Estes testes rodam na perna `backend-ml` (`pytest -m ml`).

Escopo deliberado: provar que o ramo real É TOMADO e que a partição sai
sã. O determinismo com `seed` é entrega da Fase 2 (F2-PR1, docs/15 §4) —
este arquivo é o instrumento que essa fase vai usar para provar o DoD, e
por isso o teste de repetibilidade abaixo já existe marcado como o que é:
uma constatação do comportamento ATUAL (sem seed), não uma garantia.
"""
from __future__ import annotations
import pytest
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.usecases.detect_communities import DetectCommunities

pytestmark = pytest.mark.ml

igraph = pytest.importorskip("igraph", reason="requer extra [ml]")
leidenalg = pytest.importorskip("leidenalg", reason="requer extra [ml]")


def _doc(rel: str, title: str, body: str) -> OKFDocument:
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only",
                                           generated_via="human:promote"))


@pytest.fixture
def base(settings, kb):
    """Dois blocos densos ligados por um fio único — a topologia que o
    Leiden deve separar e que gera uma ponte frágil."""
    docs = []
    for bloco, n in (("alfa", 4), ("beta", 4)):
        for i in range(n):
            vizinhos = "\n".join(
                f"- [{bloco} {j}](/concepts/{bloco}-{j}.md)"
                for j in range(n) if j != i)
            docs.append(_doc(f"concepts/{bloco}-{i}.md", f"{bloco} {i}",
                             f"# {bloco} {i}\n\n{vizinhos}\n"))
    # o fio único entre os blocos
    docs.append(_doc("concepts/ponte.md", "ponte",
                     "# ponte\n\n- [alfa 0](/concepts/alfa-0.md)\n"
                     "- [beta 0](/concepts/beta-0.md)\n"))
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    return settings


def test_ramo_leiden_real_e_tomado(base, monkeypatch):
    """Guarda contra regressão silenciosa: se o import de igraph passar a
    falhar, o produto cai no fallback SEM avisar — e a suíte, que só
    exercitava o fallback, continuaria verde."""
    tomado = {}
    original = leidenalg.find_partition

    def espiao(*a, **k):
        tomado["leiden"] = True
        return original(*a, **k)

    monkeypatch.setattr(leidenalg, "find_partition", espiao)
    DetectCommunities(base).execute()
    assert tomado.get("leiden"), (
        "o ramo Leiden de produção não foi tomado — a execução caiu no "
        "fallback de componentes com o extra [ml] instalado")


def test_leiden_real_particiona_e_grava_pontes(base):
    out = DetectCommunities(base).execute()
    assert out["communities"] >= 2, "dois blocos densos devem se separar"
    idx = connect(base.app_support / "index.db")
    atribuidas = {r["page"]: r["community"] for r in
                  idx.execute("SELECT page, community FROM communities")}
    pontes = idx.execute("SELECT COUNT(*) c FROM graph_bridges"
                         ).fetchone()["c"]
    idx.close()
    # toda página do bundle recebe comunidade (ou -1 explícito), nunca None
    assert atribuidas and all(v is not None for v in atribuidas.values())
    # os membros de um mesmo bloco caem juntos
    alfa = {atribuidas[f"concepts/alfa-{i}.md"] for i in range(4)}
    beta = {atribuidas[f"concepts/beta-{i}.md"] for i in range(4)}
    assert len(alfa) == 1 and len(beta) == 1 and alfa != beta
    assert pontes >= 1, "o fio único entre blocos reais é uma ponte frágil"


def test_repetibilidade_atual_do_leiden_sem_seed(base):
    """CONSTATAÇÃO, não garantia: hoje o Leiden roda SEM seed
    (`detect_communities.py`), então a estabilidade da partição entre
    execuções é acidental. A Fase 2 (F2-PR1) passa a exigir `seed` e
    converte esta constatação em DoD — este teste é o lugar onde isso
    será apertado, e falhar aqui é sinal de que o seed é necessário."""
    primeira = DetectCommunities(base).execute()
    segunda = DetectCommunities(base).execute()
    assert primeira["communities"] == segunda["communities"], (
        "a CONTAGEM de comunidades variou entre duas execuções sobre o "
        "mesmo bundle — evidência direta de que o seed da F2-PR1 é "
        "necessário (o rótulo inteiro já é reatribuído por construção)")
