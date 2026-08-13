"""F2-PR1 (ADR-43) — o mapa de padrões passa a ser repetível e datado.

Três entregas, e a ordem entre elas não é arbitrária: sem repetibilidade o
casamento de partições da F2-PR2 compara ruído com ruído; sem datação não há
como servir mapa velho com aviso em vez de recomputar (o que numa máquina de
8 GB é a diferença entre usável e não usável); sem poda a fila oferece
"reforce este fio" apontando para página aposentada.

O que estes testes fixam e que o `test_ml_leiden.py` deixou explicitamente
para esta fase: a repetibilidade era **constatação**, não garantia. Medido
antes da mudança, em três execuções sobre o mesmo bundle: o agrupamento se
manteve e o **rótulo inteiro trocou nas três**. Então a garantia tem duas
pernas — `seed` (a partição) e numeração canônica (o rótulo) — e as duas
precisam de ordem canônica de aresta para valer.

Os testes que exigem o Leiden real estão marcados `ml` e rodam na perna
`backend-ml` da CI; os de carimbo, poda e INV-004 valem nos dois backends,
porque é justamente no fallback que o carimbo precisa dizer a verdade.
"""
from __future__ import annotations
import pytest
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.git_store import GitStore
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import SCHEMA_VERSIONS, connect
from corpusmith.usecases.detect_communities import (LEIDEN_SEED,
                                                 DetectCommunities)
from corpusmith.usecases.diagnose import DiagnoseSystem


def _doc(rel, title, body, **extra):
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only",
                                           generated_via="human:promote",
                                           **extra))


N_ANEL = 24


@pytest.fixture
def base(settings, kb):
    """ANEL de 24 páginas — e a escolha da topologia é o ponto mais
    importante deste arquivo.

    A primeira versão usava quatro blocos densos ligados por fios únicos, e
    a suíte passava **com e sem** a canonicalização: blocos densos são
    inequívocos, o Leiden os acha em qualquer ordem de vértice, e o teste de
    determinismo era teatro. Medido no anel, onde a modularidade tem muitos
    cortes quase-empatados: 8 execuções com ordem de inserção variada dão
    **8 partições distintas**. É a topologia que torna a garantia
    falsificável.

    O anel também tem pontes frágeis por construção (todo par é um corte de
    peso 1), o que serve à poda."""
    docs = []
    for i in range(N_ANEL):
        viz = [(i + 1) % N_ANEL, (i - 1) % N_ANEL]
        corpo = "\n".join(f"- [n{j:02d}](/concepts/n{j:02d}.md)" for j in viz)
        docs.append(_doc(f"concepts/n{i:02d}.md", f"n{i:02d}",
                         f"# n{i:02d}\n\n{corpo}\n"))
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    return settings


@pytest.fixture
def com_pontes(settings, kb):
    """Quatro blocos densos em cadeia por fios únicos.

    Topologia SEPARADA do anel de propósito: o anel é 2-conexo e não tem
    ponte frágil nenhuma (remover uma aresta não parte nada), então serve ao
    determinismo e não serve à poda. Cada garantia usa a topologia que a
    torna falsificável — a alternativa era uma fixture que passa nos dois
    testes por acidente."""
    docs = []
    for b in range(4):
        for i in range(5):
            viz = "\n".join(f"- [b{b} p{j}](/concepts/b{b}-p{j}.md)"
                            for j in range(5) if j != i)
            fio = (f"\n- [b{b+1} p0](/concepts/b{b+1}-p0.md)"
                   if i == 0 and b + 1 < 4 else "")
            docs.append(_doc(f"concepts/b{b}-p{i}.md", f"b{b} p{i}",
                             f"# b{b} p{i}\n\n{viz}{fio}\n"))
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    return settings


def _mapa(settings) -> dict[str, int]:
    idx = connect(settings.app_support / "index.db")
    mapa = {r["page"]: r["community"]
            for r in idx.execute("SELECT page, community FROM communities")}
    idx.close()
    return mapa


def _snapshot(settings) -> dict:
    idx = connect(settings.app_support / "index.db")
    row = idx.execute("SELECT * FROM graph_snapshot WHERE id=1").fetchone()
    idx.close()
    return dict(row) if row else {}


# ============================================ repetibilidade (o DoD da fase)
def test_migracao_do_index_e_aditiva(base):
    """Robusto à VERSÃO, não cravado nela: o F2-PR1 subiu para 7 e o F2-PR3+4
    para 8, e um `== 7` aqui quebraria o PR seguinte sem apontar defeito
    nenhum — é a mesma classe de drift que o PR-0 atacou (G-6). O que importa
    é a migração ser aditiva."""
    assert SCHEMA_VERSIONS["index.db"] >= 7, "graph_snapshot exige v7+"
    idx = connect(base.app_support / "index.db")
    tabelas = {r["name"] for r in idx.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    idx.close()
    # aditiva: o que existia em v6 continua
    assert {"graph_snapshot", "communities", "graph_bridges", "chunks",
            "page_entities"} <= tabelas


def test_mesmo_bundle_mesma_particao_rotulo_a_rotulo(base):
    """A garantia que o `test_ml_leiden.py` deixou para esta fase: não é só
    o agrupamento, é o RÓTULO. Vale nos dois backends."""
    DetectCommunities(base).execute()
    primeiro = _mapa(base)
    for _ in range(3):
        DetectCommunities(base).execute()
        assert _mapa(base) == primeiro, "a partição mudou sem o bundle mudar"


def test_rotulo_e_canonico_pelo_menor_membro(base):
    """O rótulo não tem semântica (D-K) — mas tem de ser DERIVADO, senão
    `communities` muda sem o conhecimento mudar. Comunidade 0 é a que
    contém a página lexicograficamente menor."""
    DetectCommunities(base).execute()
    mapa = _mapa(base)
    por_comunidade: dict[int, list[str]] = {}
    for page, cid in mapa.items():
        if cid >= 0:
            por_comunidade.setdefault(cid, []).append(page)
    minimos = [min(p) for _, p in sorted(por_comunidade.items())]
    assert minimos == sorted(minimos), (
        "as comunidades não estão numeradas pelo menor membro em ordem")


@pytest.mark.ml
def test_o_seed_chega_ao_leiden_de_verdade(base, monkeypatch):
    """Guarda contra a regressão mais fácil deste PR: alguém remove o
    `seed=` e a suíte continua verde porque a topologia do teste é fácil.

    `importorskip` DENTRO do teste, não no módulo: a marca `ml` só filtra
    quando se passa `-m ml`, e a perna `backend` da CI roda a suíte inteira
    sem o extra. O `test_ml_leiden.py` faz o guard no topo porque lá TODO o
    arquivo exige o extra; aqui a maioria dos testes vale nos dois backends,
    e é justamente no fallback que o carimbo precisa dizer a verdade."""
    leidenalg = pytest.importorskip("leidenalg", reason="requer extra [ml]")
    visto = {}
    original = leidenalg.find_partition

    def espiao(*a, **k):
        visto.update(k)
        return original(*a, **k)

    monkeypatch.setattr(leidenalg, "find_partition", espiao)
    DetectCommunities(base).execute()
    assert visto.get("seed") == LEIDEN_SEED, (
        f"o Leiden foi chamado sem o seed do produto: {visto.keys()}")


def test_grafo_nao_depende_da_ordem_fisica_das_linhas(base):
    """Reembaralhando FISICAMENTE as arestas no SQLite, o mapa **e os pesos**
    saem iguais.

    O que este teste prova e o que NÃO prova, medido: remover o `ORDER BY`
    das queries e rodar isto continua verde, porque a numeração de vértice
    já é canonizada pelos `sorted()` do `_partition`. O `ORDER BY` compra a
    soma de pesos — `add_edge` acumula com `+=` e float não é associativo
    (`1.0 + 0.15 + 0.15` dá 1.3 ou 1.2999999999999998 conforme a ordem).
    Por isso a asserção compara o ADJACENTE BIT A BIT, não só a partição:
    é a única forma de este teste ficar vermelho se o `ORDER BY` sair."""
    d = DetectCommunities(base)
    idx = connect(base.app_support / "index.db")
    adj_antes = {a: dict(v) for a, v in d._weighted_graph(idx).items()}
    idx.close()
    DetectCommunities(base).execute()
    esperado = _mapa(base)
    idx = connect(base.app_support / "index.db")
    arestas = [dict(r) for r in idx.execute("SELECT * FROM graph_edges")]
    colunas = [c for c in arestas[0] if c != "id"] if arestas else []
    idx.execute("DELETE FROM graph_edges")
    marcas = ",".join("?" * len(colunas))
    for linha in reversed(arestas):        # ordem física INVERTIDA
        idx.execute(f"INSERT INTO graph_edges({','.join(colunas)}) "
                    f"VALUES ({marcas})", tuple(linha[c] for c in colunas))
    idx.commit()
    idx.close()
    DetectCommunities(base).execute()
    assert _mapa(base) == esperado, (
        "a partição depende da ordem física das linhas no SQLite")
    idx = connect(base.app_support / "index.db")
    adj_depois = {a: dict(v) for a, v in
                  DetectCommunities(base)._weighted_graph(idx).items()}
    idx.close()
    assert adj_depois == adj_antes, (
        "os pesos acumulados mudaram com a ordem física — o ORDER BY das "
        "queries do grafo é o que impede isso (float não é associativo)")


# ============================================ o carimbo
def test_carimbo_diz_de_quando_e_de_qual_head(base, kb):
    out = DetectCommunities(base).execute()
    snap = _snapshot(base)
    assert snap["bundle_head"] == GitStore(kb).head()
    assert snap["computed_at"] > 0
    assert snap["nodes"] > 0 and snap["edges"] > 0
    assert snap["communities"] == out["communities"]
    assert snap["bridges"] == out["bridges"]


def test_carimbo_declara_o_backend_que_produziu_o_mapa(base):
    """Numa máquina em que o extra `[ml]` não compilou, o produto cai no
    fallback de componentes conexos e chama o resultado de "comunidade".
    Sem este campo o doctor não tem como dizer isso em voz alta."""
    out = DetectCommunities(base).execute()
    snap = _snapshot(base)
    assert snap["backend"] in ("leiden", "components")
    assert snap["backend"] == out["backend"]
    # o seed só existe onde há aleatoriedade a fixar
    if snap["backend"] == "leiden":
        assert snap["seed"] == LEIDEN_SEED
    else:
        assert snap["seed"] is None


def test_carimbo_tem_uma_linha_so_e_e_sobrescrito(base):
    for _ in range(3):
        DetectCommunities(base).execute()
    idx = connect(base.app_support / "index.db")
    assert idx.execute("SELECT COUNT(*) c FROM graph_snapshot"
                       ).fetchone()["c"] == 1
    idx.close()


# ============================================ D-E e D-I
def test_pagina_derivada_nao_entra_no_grafo_que_a_gerou(base, kb):
    """D-E: `_CommunitySummaryPage` escreve links para os membros, e
    `rebuild_index` os converte em arestas. Sem excluir `communities/`, cada
    rodada altera o grafo da seguinte — épocas falsas de tema."""
    DetectCommunities(base).execute()
    rebuild_index(base)                      # o que a F2-PR2 passará a fazer
    idx = connect(base.app_support / "index.db")
    tem_aresta_derivada = idx.execute(
        "SELECT COUNT(*) c FROM graph_edges WHERE src LIKE 'communities/%' "
        "OR dst LIKE 'communities/%'").fetchone()["c"]
    idx.close()
    assert tem_aresta_derivada > 0, "o cenário exige arestas derivadas no índice"
    d = DetectCommunities(base)
    idx = connect(base.app_support / "index.db")
    adjacency = d._weighted_graph(idx)
    idx.close()
    assert not [n for n in adjacency if n.startswith("communities/")], (
        "página derivada entrou no grafo que a gerou")


def test_insert_de_ponte_usa_colunas_nomeadas(com_pontes):
    """D-I: `VALUES (?,?,?,?,?)` posicional quebra no instante em que o
    carimbo acrescenta coluna. Provado por execução: com uma coluna nova na
    tabela, a gravação continua funcionando."""
    idx = connect(com_pontes.app_support / "index.db")
    idx.execute("ALTER TABLE graph_bridges ADD COLUMN carimbo TEXT")
    idx.commit()
    idx.close()
    out = DetectCommunities(com_pontes).execute()
    assert out["bridges"] >= 1, "as pontes não foram gravadas"


# ============================================ a poda
def test_ponte_para_pagina_supersedida_e_podada(com_pontes, kb):
    """Ponte com endpoint aposentado é ponte para lugar nenhum — e a fila
    põe ponte frágil entre os itens de maior densidade valor/custo."""
    DetectCommunities(com_pontes).execute()
    idx = connect(com_pontes.app_support / "index.db")
    antes = [dict(r) for r in idx.execute("SELECT src, dst FROM graph_bridges")]
    idx.close()
    assert antes, "o cenário precisa de ponte para o teste valer"
    from corpusmith.usecases.curate import SupersedePage
    alvo = antes[0]["src"]
    outra = next(f"concepts/b{b}-p{i}.md" for b in range(4)
                 for i in range(5) if f"concepts/b{b}-p{i}.md" != alvo)
    SupersedePage(com_pontes, page=alvo, successor=outra).execute()
    DetectCommunities(com_pontes).execute()
    idx = connect(com_pontes.app_support / "index.db")
    depois = {(r["src"], r["dst"])
              for r in idx.execute("SELECT src, dst FROM graph_bridges")}
    idx.close()
    assert not any(alvo in par for par in depois), (
        f"ponte com endpoint supersedido ({alvo}) sobreviveu")


# ============================================ INV-004 no doctor
def test_inv004_acusa_mapa_mais_velho_que_o_head(base, kb):
    DetectCommunities(base).execute()
    rel = DiagnoseSystem(base).execute()
    assert not [f for f in rel["findings"] if f["inv"] == "INV-004"], \
        "mapa recém-computado não pode estar velho"
    BundleWriter(kb).write(
        [_doc("concepts/nova.md", "Nova", "# Nova\n\nprosa.")],
        log_kind="Creation", log_message="m", commit_message="c")
    rel = DiagnoseSystem(base).execute()
    velho = [f for f in rel["findings"] if f["inv"] == "INV-004"]
    assert velho, "o doctor não acusou mapa velho depois de um commit novo"
    assert velho[0]["severity"] == "warn"      # mapa velho não é corrupção


def test_inv004_nao_reclama_quando_nunca_houve_mapa(base):
    """Bundle novo sem `leiden` rodado não tem mapa VELHO — tem mapa
    AUSENTE, e acusar isso viraria ruído em toda instalação nova."""
    rel = DiagnoseSystem(base).execute()
    assert not [f for f in rel["findings"] if f["inv"] == "INV-004"]


def test_doctor_expoe_o_backend_do_mapa(base):
    """A informação que numa máquina de 8 GB decide se o usuário confia no
    mapa: se o `[ml]` não compilou, "comunidade" é componente conexo."""
    DetectCommunities(base).execute()
    rel = DiagnoseSystem(base).execute()
    assert rel["graph"]["backend"] in ("leiden", "components")
    assert rel["graph"]["bundle_head"]


# ============================================ o agendamento (G-5 do docs/15)
def test_o_job_leiden_e_agendado_e_com_prioridade_baixa(settings, tmp_path):
    """G-5: `leiden` estava no REGISTRY e **nunca era enfileirado** — quem
    quisesse o mapa atualizado tinha de saber que existe um job. Com o
    INV-004 isso deixa de ser detalhe: um mapa que ninguém recomputa passa a
    ser um mapa que o doctor acusa de velho para sempre, ou seja um alarme
    sem saída.

    Prioridade 7 (baixa) de propósito: o mapa cede a vez para tudo que o
    usuário pediu — numa máquina pequena essa ordem é a diferença entre um
    produto que responde e um que está sempre ocupado."""
    from corpusmith.jobs import REGISTRY
    from corpusmith.runtime.queue import JobQueue
    from corpusmith.runtime.scheduler import Scheduler
    assert "leiden" in REGISTRY, "o job precisa existir para ser agendado"
    db = connect(settings.app_support / "runtime.db")
    fila = JobQueue(db)
    agendados: list[tuple] = []
    fila.enqueue = lambda nome, payload, **kw: agendados.append(
        (nome, kw.get("priority"), kw.get("dedupe_key")))
    sch = Scheduler(fila, interval=0.01)
    # UMA passada, sem thread: `_halt` marcado ANTES nem entraria no corpo do
    # laço, então a parada acontece no `wait` do fim da primeira volta
    sch._halt.wait = lambda *a: sch._halt.set()
    import time as _t
    monday = _t.struct_time((2026, 7, 27, 3, 0, 0, 0, 208, 0))  # segunda
    original = _t.localtime
    _t.localtime = lambda *a: monday
    try:
        Scheduler.run(sch)
    finally:
        _t.localtime = original
    leiden = [a for a in agendados if a[0] == "leiden"]
    assert leiden, f"o leiden não foi agendado: {[a[0] for a in agendados]}"
    nome, prioridade, dedupe = leiden[0]
    assert prioridade == 7, "o mapa não pode competir com o que o usuário pediu"
    assert dedupe and dedupe.startswith("leiden:"), (
        "sem dedupe semanal, cada passada do scheduler enfileira de novo")
    # e é SEMANAL, não diário: o dedupe usa a semana ISO
    assert len(dedupe.split(":")[1]) >= 6
