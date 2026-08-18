"""RFC-004 — a ontologia não pode divergir do código, e a fusão não pode
decidir governança por acidente de dicionário.

Mesmo padrão de `test_architecture_toml` e `test_epistemics_toml`: o
registro declarado (`ontology.toml`) é cruzado com as constantes reais
(`kernel/ontology.py`). Aqui há, além disso, uma REGRESSÃO real — a tabela
de fraqueza de `merge_meta` tinha três valores e o produto escreve quatro.
"""
from __future__ import annotations
import itertools
import tomllib
from pathlib import Path
import pytest
from corpusmith.harness.ontology import lint, overview
from corpusmith.kernel import ontology as onto
from corpusmith.kernel.curation import merge_meta

_ROOT = Path(__file__).resolve().parents[2]


def _toml() -> dict:
    return tomllib.loads((_ROOT / "ontology.toml").read_text())


# ==================================================== o registro é honesto
def test_lint_do_registro_esta_verde():
    _, findings = lint()
    erros = [f for f in findings if f.severity == "error"]
    assert not erros, [f.to_dict() for f in erros]


def test_toml_declara_o_vocabulario_real_do_kernel():
    """Se alguém acrescentar um valor a um eixo sem declará-lo (ou o
    contrário), o registro passa a mentir sobre o código."""
    declarados = _toml()["axes"]
    for eixo, vocab in onto.AXES.items():
        assert tuple(declarados[eixo]["values"]) == vocab, eixo


def test_nenhum_valor_responde_a_duas_perguntas():
    """A propriedade que define um EIXO. É ela que `confidence` violava:
    `extracted` responde 'como derivou', `ambiguous` responde 'resolveu?'
    e `human_approved` responde 'quem autorizou' — no mesmo campo."""
    for valor in itertools.chain.from_iterable(onto.AXES.values()):
        assert len(onto.eixos_de(valor)) == 1, (
            f"`{valor}` está em {onto.eixos_de(valor)}")


def test_todo_eixo_declara_a_pergunta_que_responde():
    """Sem a pergunta não há como testar se um valor entrou no eixo por
    engano — que é exatamente como a conflação se instala."""
    for eixo in onto.AXES:
        assert onto.QUESTIONS[eixo].strip()
        assert _toml()["axes"][eixo]["question"].strip()


def test_evaluation_status_nao_e_redefinido_aqui():
    """O quarto eixo já existe fechado em `epistemic/model.py`, aplicado a
    MECANISMO. Redefini-lo criaria a segunda definição do mesmo termo — o
    defeito que este módulo combate."""
    from corpusmith.epistemic.model import EvaluationStatus
    assert "evaluation_status" not in onto.AXES
    declarado = _toml()["axes"]["evaluation_status"]
    assert declarado["applies_to"] == "mechanism"
    assert tuple(declarado["values"]) == tuple(
        e.value for e in EvaluationStatus)


def test_cada_termo_diz_o_que_NAO_e():
    """Um verbete que só diz o que a palavra significa não impede o
    sentido novo de entrar; o que segura a deriva é a fronteira."""
    for termo, corpo in _toml()["terms"].items():
        for chave in ("roots", "means", "not_means", "constrains"):
            assert corpo.get(chave, "").strip(), f"{termo}.{chave}"


# ============================== a fusão decide governança por REGRA
# A tabela inteira, célula a célula. Preferida a uma propriedade esperta
# porque a regra tem três eixos e um encoding com perda: uma propriedade
# que coubesse numa linha esconderia justamente a célula que mudou.
_TABELA = {
    ("extracted", "extracted"): "extracted",
    ("extracted", "inferred"): "inferred",       # não promove
    ("extracted", "ambiguous"): "ambiguous",     # resolução domina
    ("extracted", "human_approved"): "inferred",  # ratificação não cobre a fusão
    ("inferred", "inferred"): "inferred",
    ("inferred", "ambiguous"): "ambiguous",
    ("inferred", "human_approved"): "inferred",
    ("ambiguous", "ambiguous"): "ambiguous",
    ("ambiguous", "human_approved"): "ambiguous",
    ("human_approved", "human_approved"): "human_approved",
}


@pytest.mark.parametrize("par,esperado", sorted(_TABELA.items()))
def test_tabela_de_fusao_de_confidence(par, esperado):
    a, b = par
    assert onto.merge_confidence(a, b) == esperado


@pytest.mark.parametrize("a,b", sorted(_TABELA))
def test_fusao_e_simetrica(a, b):
    """O defeito mais barato de reproduzir e o mais caro de conviver: a
    tabela antiga ordenava por `fraqueza.get(c, 0)` e `human_approved` não
    estava nela, então empatava em 0 com `extracted` — e `max` devolve o
    PRIMEIRO dos empatados. Medido antes da correção:

        merge("human_approved", "extracted") -> "human_approved"
        merge("extracted", "human_approved") -> "extracted"

    A mesma fusão com dois resultados conforme a ordem dos argumentos, ou
    seja: conforme qual página o curador clicou primeiro.

    A asserção passa por `merge_meta` de propósito: ela é sobre o caminho
    que o produto percorre, não sobre a função nova. Verificar simetria só
    em `merge_confidence` daria verde com o defeito intacto no chamador."""
    assert merge_meta({"confidence": a}, {"confidence": b})["confidence"] \
        == merge_meta({"confidence": b}, {"confidence": a})["confidence"]


def test_ratificacao_nao_sobrevive_a_fusao_com_nao_ratificado():
    """A célula que MUDOU de comportamento. Ratificação é ato sobre um
    conteúdo; a fusão produz outro conteúdo, que ninguém ratificou.

    Falsificável: com a tabela antiga (`fraqueza` de três valores) esta
    asserção devolve `human_approved` e o teste reprova."""
    fundido = merge_meta({"confidence": "human_approved", "title": "A"},
                         {"confidence": "extracted"})
    assert fundido["confidence"] != "human_approved"
    assert fundido["confidence"] == "inferred"


def test_fusao_de_dois_ratificados_permanece_ratificada():
    fundido = merge_meta({"confidence": "human_approved"},
                         {"confidence": "human_approved"})
    assert fundido["confidence"] == "human_approved"


def test_fusao_nunca_assenta_uma_ambiguidade():
    for outro in onto.LEGACY_CONFIDENCE:
        assert merge_meta({"confidence": "ambiguous"},
                          {"confidence": outro})["confidence"] == "ambiguous"


def test_merge_meta_preserva_as_demais_regras():
    """A troca da regra de `confidence` não pode ter mexido nas outras —
    listas se unem sem duplicar e `valid_at` fica com o mais antigo."""
    fundido = merge_meta(
        {"tags": ["a", "b"], "valid_at": "2026-05-01", "title": "alvo"},
        {"tags": ["b", "c"], "valid_at": "2024-01-01", "title": "fonte"})
    assert fundido["tags"] == ["a", "b", "c"]
    assert fundido["valid_at"] == "2024-01-01"
    assert fundido["title"] == "alvo"


# ======================================================= classificação
def test_pagina_de_maquina_sem_ato_humano_e_proposta():
    """ADR-53 §3: chamar de ratificado o que ninguém ratificou é a
    alegação proibida. O default tem de cair para `proposed`."""
    eixos = onto.classificar({"generated_via": "api:compile",
                              "confidence": "extracted"})
    assert eixos["governance_status"] == "proposed"


def test_pagina_aposentada_e_retired_mesmo_tendo_sido_ratificada():
    """Aposentar é o gesto mais recente e vence a ratificação anterior —
    a página segue no bundle, só deixa de valer como afirmação corrente."""
    eixos = onto.classificar({"generated_via": "human:promote",
                              "confidence": "human_approved",
                              "superseded_by": "concepts/nova.md"})
    assert eixos["governance_status"] == "retired"


def test_classificar_devolve_valor_valido_em_todo_eixo():
    metas: list[dict] = [
        {}, {"generated_via": "human:promote"}, {"invalid_at": "2026-01-01"},
        *({"confidence": v} for v in onto.LEGACY_CONFIDENCE)]
    for meta in metas:
        for eixo, valor in onto.classificar(meta).items():
            assert onto.valido(eixo, valor), (meta, eixo, valor)


# ============================================ o registro de deriva é vivo
def test_deriva_registrada_ainda_existe_no_codigo():
    """O ponto do `marker`: uma deriva declarada aberta cujo sentido sumiu
    do código vira warn, e uma separação declarada resolvida que perdeu um
    nome vira erro. Sem isto o registro vira confissão decorativa."""
    _, findings = lint()
    assert not [f for f in findings
                if f.code in ("ontology.drift_sense_gone",
                              "ontology.drift_regressed")], \
        [f.to_dict() for f in findings]


def test_deriva_do_confidence_esta_registrada_como_paga_em_parte():
    """A entrada não pode ser fechada: os sentidos numéricos (autorrelato,
    taxa, intervalo) continuam no mesmo nome. Fechar aqui seria alegar um
    conserto que o código não tem."""
    entrada = _toml()["drift"]["confidence"]
    assert entrada["status"] == "open"
    assert len(entrada["senses"]) >= 5
    assert "kernel/ontology.py" in entrada["paid"]


def test_overview_expoe_a_mesma_fonte_da_cli():
    data = overview()
    assert data["ok"] is True
    assert {a["axis"] for a in data["axes"]} >= set(onto.AXES)
    assert data["version"]
