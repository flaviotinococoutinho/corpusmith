"""V6 — a ficha do conceito: custo, tempo, trade-offs e ganhos (RFC-006).

A capacidade que o pitch promete ("quanto custa adotar essa ideia?") é
também a mais fácil de entregar desonesta — e a RFC nomeou a armadilha:
**autocertificação**. O produto tem constantes internas de "valor"
(0.9, 0.85) que ele mesmo declara não calibradas — "o detector não mede
importância" (`next_actions.py`). Apresentá-las como ganho medido seria
cometer, na superfície de venda, exatamente o `self_reported`-só que o
contrato-mestre proíbe aos mecanismos.

Então a ficha declara o que MEDIU (tempo de leitura, edições no Git,
sinais de dificuldade, casos práticos declarados por humano, garantias
dos contratos) e diz em voz alta o que NÃO tem (ganho, valor, ROI).
Nenhum campo de "benefício" existe para ser preenchido depois — a
ausência é estrutural, não um TODO.
"""
from __future__ import annotations

import pytest

from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.usecases.concept_sheet import ConceptSheet


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


# ------------------------------------------------------- o que a ficha É
def test_ficha_reune_as_quatro_projecoes_da_re_mira(settings, kb):
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nUm conceito."))
    ficha = ConceptSheet(settings, "concepts/x.md").execute()
    assert ficha["page"] == "concepts/x.md"
    assert ficha["title"] == "X"
    for chave in ("cost", "stability", "difficulty", "applications",
                  "guarantees", "not_measured"):
        assert chave in ficha, chave


def test_custo_e_TEMPO_DE_LEITURA_medido_no_texto(settings, kb):
    """A metade honesta do trade-off: minutos, com a mesma constante da
    fila (150 wpm, piso de 2 min) — não uma segunda definição de custo."""
    from corpusmith.usecases.plan_attention import _MIN_COST, _WPM
    corpo = "# Y\n\n" + ("palavra " * 900)
    _write(settings, kb, _doc("concepts/y.md", "Y", corpo))
    ficha = ConceptSheet(settings, "concepts/y.md").execute()
    assert ficha["cost"]["read_minutes"] == pytest.approx(
        round(len(corpo.split()) / _WPM, 1), abs=0.2)
    assert ficha["cost"]["read_minutes"] >= _MIN_COST
    assert "150" in ficha["cost"]["how"]        # o método viaja com o número


def test_pagina_inexistente_e_erro_claro_nao_ficha_vazia(settings, kb):
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    with pytest.raises(KeyError, match="não existe"):
        ConceptSheet(settings, "concepts/fantasma.md").execute()


# ------------------------------------------ o que a ficha RECUSA declarar
def test_ficha_NAO_tem_campo_de_ganho_nem_de_valor(settings, kb):
    """A armadilha nomeada pela RFC-006, presa por teste: nenhum campo de
    benefício existe para alguém preencher com constante não calibrada.
    Se um dia `value`/`gain`/`roi` aparecer aqui, isto reprova junto."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    ficha = ConceptSheet(settings, "concepts/x.md").execute()
    proibidos = {"value", "gain", "roi", "benefit", "ganho", "beneficio"}
    assert not (proibidos & set(ficha))
    assert not (proibidos & set(ficha["cost"]))


def test_o_que_NAO_foi_medido_vem_dito_na_propria_ficha(settings, kb):
    """Dizer "não medimos ganho" é parte do produto, não uma omissão a
    ser explicada em nota de rodapé."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    nao_medido = ConceptSheet(settings, "concepts/x.md").execute()[
        "not_measured"]
    junto = " ".join(nao_medido).lower()
    assert "ganho" in junto
    assert "importância" in junto or "importancia" in junto


def test_ficha_carrega_as_ressalvas_dos_contratos_que_usa(settings, kb):
    """Cada número da ficha vem de um mecanismo com contrato; as
    `misinterpretations` dele viajam JUNTO do número, não numa página
    separada que ninguém abre."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    g = ConceptSheet(settings, "concepts/x.md").execute()["guarantees"]
    ids = {item["mechanism_id"] for item in g}
    assert {"editorial_stability", "explanation_difficulty",
            "typed_application_edges"} <= ids
    assert all(item["misinterpretations"] for item in g)
    estab = next(i for i in g if i["mechanism_id"] == "editorial_stability")
    # a ressalva que importa para quem lê a ficha: estável ≠ verdadeiro.
    # (Assertivo sobre o SENTIDO, com a palavra que o contrato de fato
    # usa — a primeira versão deste teste chutou "correto" e reprovou.)
    assert "verdadeiro" in " ".join(estab["misinterpretations"]).lower()


# ----------------------------------------------- composição das projeções
def test_estabilidade_entra_com_o_sentido_declarado(settings, kb):
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    e = ConceptSheet(settings, "concepts/x.md").execute()["stability"]
    assert e["edits"] >= 1                     # o commit de criação conta
    assert "edição" in e["means"].lower()      # NUNCA "correto"


def test_dificuldade_entra_com_a_distincao_medida_vs_sem_sinal(settings, kb):
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    d = ConceptSheet(settings, "concepts/x.md").execute()["difficulty"]
    assert d["measured"] is False
    assert "não" in d["means"].lower() and "fácil" in d["means"].lower()


def test_aplicacoes_entram_com_a_medicao_do_nivel(settings, kb):
    _write(settings, kb,
           _doc("concepts/x.md", "X",
                '# X\n\nVer [Caso](/runbooks/caso.md "rel:applies_to").'),
           _doc("runbooks/caso.md", "Caso", "# Caso\n\nPrático."))
    a = ConceptSheet(settings, "concepts/x.md").execute()["applications"]
    assert [c["page"] for c in a["cases"]] == ["runbooks/caso.md"]
    assert a["measurement"]["edges"] == 1


# ------------------------------------------------- a borda LLM (desligada)
def test_a_prosa_de_venda_e_DESLIGADA_por_default(settings, kb):
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    ficha = ConceptSheet(settings, "concepts/x.md").execute()
    assert ficha["prose"] is None
    assert ficha["prose_enabled"] is False


def test_prosa_ligada_re_anexa_as_ressalvas_DEPOIS_do_modelo(settings, kb):
    """A regra que a RFC fixou: as ressalvas são re-anexadas
    DETERMINISTICAMENTE após a geração, fora da região que o modelo pode
    editar. Um modelo que "esqueça" as ressalvas não consegue publicá-las
    fora — elas não passam por ele."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    ficha = ConceptSheet(settings, "concepts/x.md",
                         prose=True, _router=_RouterFake("VENDA VENDA")
                         ).execute()
    assert ficha["prose"].startswith("VENDA VENDA")
    assert "não medimos" in ficha["prose"].lower()
    assert "ganho" in ficha["prose"].lower()


def test_modelo_indisponivel_degrada_para_a_ficha_seca(settings, kb):
    """Sem modelo, a ficha determinística continua inteira — a prosa é
    ENFEITE da projeção, nunca o produto."""
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    ficha = ConceptSheet(settings, "concepts/x.md",
                         prose=True, _router=_RouterFake(None)).execute()
    assert ficha["prose"] is None
    assert ficha["stability"]["edits"] >= 1
    assert ficha["prose_error"]


def test_a_prosa_nunca_toca_o_canonico(settings, kb):
    """A-3/A-4: LLM lê projeções e NUNCA escreve no canônico. O HEAD do
    Git antes e depois é o mesmo — a lição do C6, aplicada antes de o
    defeito existir."""
    from corpusmith.okf.git_store import GitStore
    _write(settings, kb, _doc("concepts/x.md", "X", "# X\n\nTexto."))
    antes = GitStore(kb).head()
    ConceptSheet(settings, "concepts/x.md", prose=True,
                 _router=_RouterFake("prosa")).execute()
    assert GitStore(kb).head() == antes


class _RouterFake:
    """Roteador de mentira: `None` simula modelo indisponível."""

    def __init__(self, resposta):
        self._resposta = resposta

    def complete(self, prompt, **kwargs):
        if self._resposta is None:
            from corpusmith.models.router import ModelUnavailable
            raise ModelUnavailable("sem modelo (teste)")
        return self._resposta
