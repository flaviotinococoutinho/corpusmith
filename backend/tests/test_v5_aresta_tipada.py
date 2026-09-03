"""V5 — a ponte abstrato→prático (RFC-006, docs/18 §10 item 6).

Medido ANTES de escrever qualquer linha: o `rel` já existia ponta a ponta
no CANÔNICO (`md_link(..., rel)` escreve `rel:x` no título do link e
`Link.rel` o lê de volta), mas morria na projeção — `rebuild_index`
gravava `graph_edges.kind` com a SINTAXE (`markdown`/`wikilink`) e jogava
a relação fora. Consequência: um curador podia declarar "este conceito se
aplica a este caso" e nenhum leitor do produto conseguia responder com
isso. E o vocabulário era ABERTO: `rel:qualquer_coisa` entrava no
canônico sem ninguém recusar.

Este pacote fecha os três buracos e declara o preço do nível (docs/28
§2): a aresta é de PÁGINA, então "aplica-se a" afirma que a página
inteira se aplica — e a medição desse erro é justamente o que a RFC-004
§6 pede antes de reabrir o nível da afirmação.
"""
from __future__ import annotations

import pytest

from corpusmith.kernel.semantics import (RELACOES, direcao, e_relacao,
                                         relacao_ou_none)
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.usecases.curate import LinkPages
from corpusmith.usecases.practical_cases import PracticalCases


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


# ------------------------------------------------- o vocabulário (puro)
def test_vocabulario_e_fechado_e_cada_relacao_declara_sua_pergunta():
    assert set(RELACOES) == {"applies_to", "exemplifies", "refines"}
    for nome, verbete in RELACOES.items():
        assert verbete["pergunta"] and verbete["nao_significa"], nome


def test_relacao_desconhecida_nao_e_relacao():
    assert e_relacao("applies_to") is True
    assert e_relacao("ponte") is False          # a topológica não entra aqui
    assert e_relacao("") is False
    assert e_relacao(None) is False


def test_relacao_ou_none_tolera_o_legado():
    """Leitura TOLERANTE, escrita ESTRITA: um bundle antigo com
    `rel:whatever` não pode derrubar o rebuild — a relação desconhecida
    vira "não tipada", que é a leitura honesta."""
    assert relacao_ou_none("refines") == "refines"
    assert relacao_ou_none("whatever") is None
    assert relacao_ou_none(None) is None


def test_direcao_de_cada_relacao_e_declarada():
    """Sem direção declarada, "A applies_to B" e "B applies_to A"
    seriam a mesma coisa para quem lê — e são opostas."""
    assert direcao("applies_to") == "abstract_to_practical"
    assert direcao("exemplifies") == "practical_to_abstract"
    assert direcao("refines") == "abstract_to_abstract"


def test_ponte_topologica_nao_entra_no_vocabulario_semantico():
    """A armadilha nomeada pela RFC-006: dois sentidos de "ponte" no mesmo
    nome. A ponte do grafo é estrutura (`graph_bridges`); esta camada é
    sobre SIGNIFICADO — se um dia "bridge" entrar aqui, isto reprova."""
    assert not {"bridge", "ponte"} & set(RELACOES)


# --------------------------------------------- o ato humano (escrita)
def test_ato_link_aceita_relacao_do_vocabulario(settings, kb):
    _write(settings, kb,
           _doc("concepts/idempotencia.md", "Idempotência",
                "# Idempotência\n\nConceito."),
           _doc("runbooks/retry.md", "Retry de jobs",
                "# Retry de jobs\n\nCaso prático."))
    r = LinkPages(settings, "concepts/idempotencia.md", "runbooks/retry.md",
                  rel="applies_to").execute(dry_run=False)
    assert r["commit"]
    corpo = (kb / "bundle" / "concepts/idempotencia.md").read_text()
    assert 'rel:applies_to' in corpo


def test_ato_link_RECUSA_relacao_fora_do_vocabulario(settings, kb):
    """Vocabulário sem fronteira é o defeito que o `ontology.toml` existe
    para impedir — e o canônico é para sempre: um `rel:` inventado hoje é
    dívida de vocabulário que ninguém sabe interpretar amanhã."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nx."),
           _doc("concepts/b.md", "B", "# B\n\ny."))
    with pytest.raises(ValueError, match="relação"):
        LinkPages(settings, "concepts/a.md", "concepts/b.md",
                  rel="serve_pra").execute(dry_run=True)


def test_link_sem_relacao_continua_valendo(settings, kb):
    """Relação tipada é ACRÉSCIMO: o link simples (só "estas duas páginas
    se falam") continua sendo um ato legítimo."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nx."),
           _doc("concepts/b.md", "B", "# B\n\ny."))
    assert LinkPages(settings, "concepts/a.md",
                     "concepts/b.md").execute(dry_run=False)["commit"]


def test_preview_declara_o_preco_do_NIVEL(settings, kb):
    """A armadilha em pessoa (docs/28 §2): a aresta é de PÁGINA, então
    "aplica-se a" afirma que a página INTEIRA se aplica. O preview diz
    isso ANTES do efeito, em vez de o produto fingir precisão."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nx."),
           _doc("runbooks/b.md", "B", "# B\n\ny."))
    p = LinkPages(settings, "concepts/a.md", "runbooks/b.md",
                  rel="applies_to").execute(dry_run=True)
    assert "página inteira" in p["preview"]["note"]


# ------------------------------------------------ a projeção (leitura)
def test_relacao_chega_ao_grafo(settings, kb):
    _write(settings, kb,
           _doc("concepts/idem.md", "Idempotência",
                '# Idempotência\n\nVer [Retry](/runbooks/retry.md '
                '"rel:applies_to").'),
           _doc("runbooks/retry.md", "Retry", "# Retry\n\nCaso."))
    idx = connect(settings.app_support / "index.db")
    linhas = [dict(r) for r in idx.execute(
        "SELECT src, dst, rel FROM graph_edges WHERE rel IS NOT NULL")]
    idx.close()
    assert linhas == [{"src": "concepts/idem.md", "dst": "runbooks/retry.md",
                       "rel": "applies_to"}]


def test_relacao_desconhecida_no_corpo_nao_derruba_o_rebuild(settings, kb):
    """Escrita estrita não protege o que JÁ está no bundle (nem prosa
    escrita à mão). O rebuild grava `rel` nulo — nunca estoura."""
    _write(settings, kb,
           _doc("concepts/a.md", "A",
                '# A\n\nVer [B](/concepts/b.md "rel:inventada").'),
           _doc("concepts/b.md", "B", "# B\n\ny."))
    idx = connect(settings.app_support / "index.db")
    (linha,) = [dict(r) for r in idx.execute(
        "SELECT rel FROM graph_edges WHERE src='concepts/a.md'")]
    idx.close()
    assert linha["rel"] is None


# --------------------------------- a consulta (e a medição do RFC-004 §6)
def test_consulta_responde_que_caso_pratico_sustenta_o_conceito(settings, kb):
    _write(settings, kb,
           _doc("concepts/idem.md", "Idempotência",
                '# Idempotência\n\nVer [Retry](/runbooks/retry.md '
                '"rel:applies_to").'),
           _doc("runbooks/retry.md", "Retry", "# Retry\n\nCaso prático."))
    r = PracticalCases(settings, "concepts/idem.md").execute()
    assert [(c["page"], c["rel"]) for c in r["cases"]] == [
        ("runbooks/retry.md", "applies_to")]


def test_consulta_enxerga_a_relacao_INVERSA(settings, kb):
    """Quem escreveu `exemplifies` na página prática respondeu à mesma
    pergunta pelo outro lado — exigir que o curador escreva na direção
    "certa" seria burocracia disfarçada de ontologia."""
    _write(settings, kb,
           _doc("concepts/idem.md", "Idempotência", "# Idempotência\n\nx."),
           _doc("runbooks/retry.md", "Retry",
                '# Retry\n\nVer [Idempotência](/concepts/idem.md '
                '"rel:exemplifies").'))
    r = PracticalCases(settings, "concepts/idem.md").execute()
    assert [(c["page"], c["rel"], c["via"]) for c in r["cases"]] == [
        ("runbooks/retry.md", "exemplifies", "inversa")]


def test_link_sem_relacao_nao_vira_caso_pratico(settings, kb):
    """"Estas páginas se falam" não é "esta se aplica àquela" — misturar
    as duas devolveria o grafo inteiro como resposta prática."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nVer [B](/concepts/b.md)."),
           _doc("concepts/b.md", "B", "# B\n\ny."))
    assert PracticalCases(settings, "concepts/a.md").execute()["cases"] == []


def test_a_consulta_MEDE_o_custo_da_granularidade_de_pagina(settings, kb):
    """A medição que a RFC-004 §6 exige antes de reabrir o nível 3.

    Uma página-alvo que carrega DOIS sujeitos fortes distintos torna
    "aplica-se a esta página" ambíguo: não se sabe a QUAL afirmação o
    conceito se aplica. A fração dessas é o custo medido — em número, não
    em opinião."""
    _write(settings, kb,
           _doc("concepts/idem.md", "Idempotência",
                '# Idempotência\n\nVer [Multi](/runbooks/multi.md '
                '"rel:applies_to") e [Um](/runbooks/um.md '
                '"rel:applies_to").'),
           _doc("runbooks/multi.md", "Multi",
                "# Multi\n\nA ISO 27001 exige X; a ISO 9001 exige Y."),
           _doc("runbooks/um.md", "Um", "# Um\n\nA ISO 27001 exige X."))
    m = PracticalCases(settings, "concepts/idem.md").execute()["measurement"]
    assert m["edges"] == 2
    assert m["ambiguous_targets"] == 1          # só `multi.md`
    assert m["ambiguous_fraction"] == 0.5
    assert "afirmação" in m["note"]


def test_medicao_sem_arestas_nao_inventa_fracao(settings, kb):
    """Zero aresta ⇒ zero medição. Devolver 0.0 como se fosse "medido e
    ótimo" é o mesmo erro que o `medida=false` da V4 impede."""
    _write(settings, kb, _doc("concepts/só.md", "Só", "# Só\n\nx."))
    m = PracticalCases(settings, "concepts/só.md").execute()["measurement"]
    assert m["edges"] == 0
    assert m["ambiguous_fraction"] is None


def test_applies_to_ENTRANDO_nao_e_caso_pratico_deste_conceito(settings, kb):
    """Achado por MUTAÇÃO (remover o filtro de direção sobrevivia).

    Uma aresta `applies_to` que APONTA para esta página diz o contrário
    do que a consulta pergunta: significa que o conceito da OUTRA página
    se aplica a esta — ou seja, esta aqui é o caso, não o conceito.
    Listá-la como "caso prático" inverteria a leitura e devolveria
    conceitos onde o usuário pediu aplicações. Só a inversa declarada
    (`exemplifies`, prático→abstrato) atravessa."""
    _write(settings, kb,
           _doc("concepts/alvo.md", "Alvo", "# Alvo\n\nConceito."),
           _doc("concepts/outro.md", "Outro",
                '# Outro\n\nVer [Alvo](/concepts/alvo.md "rel:applies_to").'))
    assert PracticalCases(settings, "concepts/alvo.md").execute()["cases"] == []


def test_refines_entrando_tambem_nao_atravessa(settings, kb):
    """`refines` é abstrato→abstrato: nenhuma das pontas é "o caso"."""
    _write(settings, kb,
           _doc("concepts/alvo.md", "Alvo", "# Alvo\n\nConceito."),
           _doc("concepts/detalhe.md", "Detalhe",
                '# Detalhe\n\nVer [Alvo](/concepts/alvo.md "rel:refines").'))
    assert PracticalCases(settings, "concepts/alvo.md").execute()["cases"] == []
