"""Q-1 — a superfície de estudo chega ao cockpit, e o refresh ganha UM dono.

Três capacidades da re-mira (V3 "o que menos muda", V5 "onde se aplica",
V6 "a ficha") saíram CLI/facade-only: a reincidência medida da patologia
de `docs/17` §1.4, *"o backend termina onde a interface começa"*. Este
arquivo prende as duas metades da correção.

**1. As rotas existem e são LEITURA.** `/cockpit/sheet`,
`/cockpit/stability` e `/cockpit/applications` passam pela facade
(INV-ARCH-004) e nenhuma delas recomputa projeção.

**2. O refresh tem um dono só.** Antes daqui havia TRÊS caminhos para os
mesmos números: o CLI recomputava e persistia, o painel lia o persistido,
e a `ConceptSheet` recomputava ao montar (`git log` da história inteira +
lint do corpus inteiro, por abertura de ficha). Três donos do mesmo valor
podem dar três respostas para a mesma pergunta na mesma máquina — e a
terceira cobrava o preço mais alto no momento mais sensível. Agora quem
escreve é o comando de refresh; quem lê passa por
`retrieval/projections.py`, e o teste que prova isso é o que faz
`Compute*` EXPLODIR e mostra a ficha inteira saindo mesmo assim.

**3. "Ainda não calculado" ≠ "nada observado".** São dois vazios com
significados opostos: o primeiro não diz nada sobre página nenhuma, o
segundo é um resultado. Empatá-los vende silêncio como medição — o avesso
da autocertificação, e igualmente falso. `computed` é o campo que os
separa, e ele viaja em toda projeção lida.
"""
from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from corpusmith.api.system import build_app
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval import projections
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.runtime.events import EventBus
from corpusmith.runtime.governor import Governor
from corpusmith.runtime.queue import JobQueue
from corpusmith.usecases.compute_difficulty import ComputeDifficulty
from corpusmith.usecases.compute_stability import ComputeStability
from corpusmith.usecases.concept_sheet import ConceptSheet

TOKEN = "test-token"


@pytest.fixture
def client_api(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    connect(settings.app_support / "index.db").close()
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-corpusmith-auth": TOKEN})
        yield c


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _write(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _refresh(settings):
    ComputeStability(settings).execute()
    ComputeDifficulty(settings).execute()


# =========================================== 1. o dono único do refresh
def test_a_ficha_LE_a_projecao_e_nao_a_recomputa(settings, kb, monkeypatch):
    """A prova por EXECUÇÃO de que o terceiro recomputador morreu.

    Falsificável e falsificada: com a ficha chamando `Compute*` (o desenho
    anterior), este teste estoura o `AssertionError` plantado. Ele não
    olha para o tempo nem para o número de queries — olha para a única
    coisa que não admite interpretação: a função que recomputa não é
    chamada."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    _refresh(settings)

    def recusa(self):
        raise AssertionError(
            "a ficha recomputou uma projeção — o refresh tem UM dono "
            "(Q-1), e a abertura de tela não é ele")

    monkeypatch.setattr(ComputeStability, "execute", recusa)
    monkeypatch.setattr(ComputeDifficulty, "execute", recusa)
    ficha = ConceptSheet(settings, "concepts/x.md").execute()
    assert ficha["stability"]["edits"] >= 1
    assert ficha["difficulty"]["computed"] is True


def test_a_ficha_diz_o_frescor_da_projecao_que_serve(settings, kb):
    """O preço honesto de ler em vez de recomputar: a ficha pode servir
    número velho, e então ela DIZ que é velho.

    O bundle andar move o HEAD sem mover a projeção — e o checkpoint
    `stability` acusa `stale`. Sem este campo, a escolha de ler viraria
    uma mentira silenciosa em vez de um custo declarado."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    _refresh(settings)
    assert ConceptSheet(settings, "concepts/x.md").execute()[
        "stability"]["freshness"]["state"] == "fresh"
    _write(settings, kb, _doc("concepts/z.md", "Z", "# Z\n\nOutro texto."))
    e = ConceptSheet(settings, "concepts/x.md").execute()["stability"]
    assert e["freshness"]["state"].startswith("stale")
    assert e["refresh"] == "corpusmith stability"


# ============================= 2. "ainda não calculado" ≠ "nada observado"
def test_nunca_computado_nao_se_disfarca_de_nada_observado(settings, kb):
    """Os dois vazios, lado a lado, no mesmo teste — que é o único jeito
    de garantir que continuam distintos.

    Sem refresh: `computed=False` e os números são `None` (não `0`, não
    `False`). Com refresh e sem sinal: `computed=True`, `measured=False`.
    Um `0` no primeiro caso diria "página nunca editada" sobre uma
    projeção que nunca rodou."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    antes = ConceptSheet(settings, "concepts/x.md").execute()
    assert antes["stability"]["computed"] is False
    assert antes["stability"]["edits"] is None
    assert antes["difficulty"]["computed"] is False
    assert antes["difficulty"]["score"] is None

    _refresh(settings)
    depois = ConceptSheet(settings, "concepts/x.md").execute()
    assert depois["stability"]["computed"] is True
    assert depois["stability"]["edits"] >= 1
    assert depois["difficulty"]["computed"] is True
    assert depois["difficulty"]["measured"] is False   # rodou, nada observado


def test_divergencia_vazia_nao_e_divergencia_nao_calculada(settings, kb):
    """A tabela de divergência VAZIA é o estado normal de um corpus
    saudável — lê-la como "nunca calculado" acusaria falso em toda base
    sem conflito. Por isso `computed` da divergência vem da MESMA passada
    que escreve a dificuldade, não da própria tabela."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    assert projections.divergence(settings, "concepts/x.md")[
        "computed"] is False
    _refresh(settings)
    v = projections.divergence(settings, "concepts/x.md")
    assert v["computed"] is True and v["conflicts"] == []


# =================================== 3. as duas linhas novas do pitch
def test_onde_diverge_nomeia_o_GRUPO_sem_dizer_quem_tem_razao(settings, kb):
    """Duas páginas sob o mesmo DOI, sem sucessão: o lint acusa, e a ficha
    de CADA UMA aponta a outra. Dizer só "há divergência" deixaria o
    leitor sem saber onde procurar; dizer qual está certa seria um juízo
    que nenhum detector pode fazer (é ato humano)."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nDOI: 10.1000/xyz123. Um."),
           _doc("concepts/b.md", "B", "# B\n\nDOI: 10.1000/xyz123. Outro."))
    _refresh(settings)
    v = ConceptSheet(settings, "concepts/a.md").execute()["divergence"]
    assert v["conflicts"], "o grupo do mesmo identificador não chegou à ficha"
    assert "concepts/b.md" in v["conflicts"][0]["with_pages"]
    assert "concepts/a.md" not in v["conflicts"][0]["with_pages"]
    assert "não diz qual" in v["means"]
    # o avesso: a ficha de B aponta A
    outra = ConceptSheet(settings, "concepts/b.md").execute()["divergence"]
    assert "concepts/a.md" in outra["conflicts"][0]["with_pages"]


def test_sob_qual_lente_declara_o_salto_de_nivel(settings, kb):
    """A linha "sob qual lente" lê MENÇÕES (`page_entities`) e afirma algo
    sobre a PÁGINA — o salto de nível de `docs/28` §2. Declará-lo é o
    preço de usá-lo mesmo assim; escondê-lo seria a patologia."""
    _write(settings, kb,
           _doc("concepts/x.md", "X", "# X\n\nUsamos PostgreSQL e SQLite."))
    lente = ConceptSheet(settings, "concepts/x.md").execute()["lens"]
    assert lente["level"] == "mention"
    assert "menção" in lente["means"] or "MENÇÕES" in lente["means"]
    canonicos = {e["canonical"] for e in lente["entities"]}
    assert "PostgreSQL" in canonicos


def test_indice_que_rodou_sem_achar_entidade_nao_e_indice_ausente(
        settings, kb):
    """O mesmo erro dos dois vazios, cometido do outro lado — e este eu
    cometi: usar `page_entities` como testemunha de "o índice rodou" faz
    uma página sem identidade reconhecível reportar "ainda não calculado"
    sobre um índice FRESCO. Achado numa execução real sobre bundle
    sintético, não em revisão de código. A testemunha certa é
    `page_index_state`: ela diz que o índice viu a página, ache ele o que
    achar."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nnada aqui."))
    lente = projections.lens(settings, "concepts/x.md")
    assert lente["computed"] is True          # o índice rodou
    assert lente["entities"] == []            # e não achou identidade


def test_a_lente_separa_base_de_sentido(settings, kb):
    """O qualificador curado da V2 é o que responde "sob qual lente":
    `Entropia (física)` é `Entropia` VISTA pela física. Sem separar base e
    sentido, a ficha imprimiria o parêntese como parte do nome."""
    from corpusmith.normalize.gazetteer import base, sentido
    assert base("Entropia (física)") == "Entropia"
    assert sentido("Entropia (física)") == "física"
    assert sentido("PostgreSQL") is None


# ============================================= 4. as rotas do cockpit
def test_as_tres_rotas_de_estudo_respondem_e_nao_recomputam(
        client_api, settings, kb, monkeypatch):
    """A ponta que faltava: as três capacidades alcançáveis pelo app.

    O `monkeypatch` que faz `Compute*` explodir vale para as rotas pelo
    mesmo motivo que vale para a ficha — uma rota que recompute devolve o
    número certo e cobra o corpus inteiro por request."""
    _write(settings, kb,
           _doc("concepts/x.md", "X",
                '# X\n\nVer [Caso](/runbooks/c.md "rel:applies_to").'),
           _doc("runbooks/c.md", "Caso", "# Caso\n\nPrático."))
    _refresh(settings)

    def recusa(self):
        raise AssertionError("rota de leitura recomputou projeção (Q-1)")

    monkeypatch.setattr(ComputeStability, "execute", recusa)
    monkeypatch.setattr(ComputeDifficulty, "execute", recusa)

    ficha = client_api.get("/cockpit/sheet?page=concepts/x.md")
    assert ficha.status_code == 200
    assert ficha.json()["title"] == "X"
    assert ficha.json()["not_measured"]

    estab = client_api.get("/cockpit/stability")
    assert estab.status_code == 200
    assert estab.json()["computed"] is True
    assert "edição" in estab.json()["means"].lower()

    apps = client_api.get("/cockpit/applications?page=concepts/x.md")
    assert apps.status_code == 200
    assert [c["page"] for c in apps.json()["cases"]] == ["runbooks/c.md"]


def test_ficha_de_pagina_inexistente_e_404_nomeado(client_api, settings, kb):
    """Erro de borda com código estável (AGENTS §9) — nunca 500, nunca
    ficha vazia que parece "conceito sem nada medido"."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    r = client_api.get("/cockpit/sheet?page=concepts/fantasma.md")
    assert r.status_code == 404
    assert "não existe" in r.json()["detail"]


def test_stability_view_nao_calculada_diz_o_comando_que_calcula(
        client_api, settings, kb):
    """Painel aberto numa instalação nova: a resposta honesta é "ainda não
    calculado" com o comando ao lado, não uma lista vazia que insinua
    "nenhuma página é estável"."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    corpo = client_api.get("/cockpit/stability").json()
    assert corpo["computed"] is False
    assert corpo["stability"] == []
    assert corpo["refresh"] == "corpusmith stability"


# ================================== 5. a passada de lint tem um dono só
def test_a_divergencia_e_persistida_na_MESMA_passada_da_dificuldade(
        settings, kb):
    """Duas projeções, uma passada — e a mesma transação.

    O lint percorre o corpus inteiro; rodá-lo duas vezes custaria o dobro
    e as duas leituras poderiam discordar entre si. `ComputeDifficulty`
    devolve a contagem para que a divergência não possa ser escrita em
    silêncio."""
    from corpusmith.runtime.db import connect
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nDOI: 10.1000/xyz123. Um."),
           _doc("concepts/b.md", "B", "# B\n\nDOI: 10.1000/xyz123. Outro."))
    resultado = ComputeDifficulty(settings).execute()
    assert resultado["divergences"] > 0
    idx = connect(settings.app_support / "index.db")
    try:
        linhas = idx.execute(
            "SELECT COUNT(*) c FROM page_divergence").fetchone()["c"]
    finally:
        idx.close()
    assert linhas == resultado["divergences"]


def test_recomputar_nao_acumula_divergencia(settings, kb):
    """Idempotência da projeção: rodar duas vezes sobre o mesmo corpus dá
    a mesma tabela. Sem o DELETE, a ficha mostraria o mesmo conflito
    repetido uma vez por execução do refresh."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nDOI: 10.1000/xyz123. Um."),
           _doc("concepts/b.md", "B", "# B\n\nDOI: 10.1000/xyz123. Outro."))
    primeira = ComputeDifficulty(settings).execute()["divergences"]
    segunda = ComputeDifficulty(settings).execute()["divergences"]
    assert primeira == segunda > 0
    v = projections.divergence(settings, "concepts/a.md")
    assert len(v["conflicts"]) == len({(c["rule"], c["identifier"])
                                       for c in v["conflicts"]})


def test_o_painel_de_indicadores_distingue_os_dois_vazios(settings, kb):
    """O mesmo defeito da ficha vivia no Indicadores: lista de dificuldade
    vazia era descrita como "nada observado ainda" mesmo quando a
    projeção nunca havia rodado. `difficulty_computed` separa os casos."""
    from corpusmith.retrieval import observatory
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    assert observatory.insights(settings)["gaps"][
        "difficulty_computed"] is False
    ComputeDifficulty(settings).execute()
    assert observatory.insights(settings)["gaps"][
        "difficulty_computed"] is True


@pytest.mark.parametrize("contrato", ["alias_conflict", "factual_conflict"])
def test_as_linhas_novas_trouxeram_os_contratos_delas(settings, kb, contrato):
    """A lista `_CONTRATOS` é FECHADA de propósito: número na ficha sem
    contrato ao lado é valor sem qualificação, que é o gesto que esta
    capacidade existe para não fazer."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    g = ConceptSheet(settings, "concepts/x.md").execute()["guarantees"]
    item = next(i for i in g if i["mechanism_id"] == contrato)
    assert item["misinterpretations"]
