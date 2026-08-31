"""Reforço dos dois registros normativos — epistemologia e ontologia.

**Epistemologia.** `PROMISED_MECHANISMS` guardava duas dívidas que
`docs/14` declarou obrigatórias e que apareciam como `warn` em TODA
execução do lint: `temporal_partition` e `inferred_cooccurrence_edges`.
Medido antes de escrever qualquer contrato: **os dois mecanismos
EXISTEM no código** (`retrieval/streams.py:_valid_at` particiona por
`as_of`; `usecases/detect_communities.py` materializa aresta por
co-menção com teto anti-hub). A dívida era de CONTRATO, não de
funcionalidade — e um aviso que nunca some ensina a ignorar a saída do
lint, que é o oposto do que o registro existe para fazer.

**Ontologia.** O registro tinha um buraco de completude que a
epistemologia já havia fechado com `EXPECTED_MECHANISMS` (achado G-10):
o lint cruzava os EIXOS declarados com o código, mas **nada** cobrava a
declaração de um vocabulário fechado NOVO. Foi o que aconteceu nesta
mesma trilha: a V5 criou `RELACOES` e a C6 criou `SideEffect` — dois
vocabulários fechados que entram no canônico e no registro epistêmico —
e o léxico não cresceu um verbete. Silêncio do lint sobre vocabulário
novo é exatamente a deriva que ele existe para impedir.
"""
from __future__ import annotations

import pytest

from corpusmith.harness import ontology as onto_lint
from corpusmith.harness.epistemics import (EXPECTED_MECHANISMS,
                                           PROMISED_MECHANISMS, lint,
                                           load_registry)
from corpusmith.kernel import ontology as onto


# ===================================================== epistemologia
def test_as_duas_dividas_prometidas_foram_PAGAS():
    """O gesto que registra a quitação é mover o nome entre as listas —
    o mesmo ritual de `attention_queue` (F3-PR2) e `factual_conflict`
    (F4-PR3b). `PROMISED` vazia significa: `docs/14` §4 e §5 não têm
    mais contrato prometido e não escrito."""
    assert PROMISED_MECHANISMS == ()
    assert {"temporal_partition", "inferred_cooccurrence_edges"} <= set(
        EXPECTED_MECHANISMS)


def test_lint_para_de_avisar_o_que_nao_e_mais_divida():
    """Aviso que sobrevive à entrega ensina a ignorar o lint."""
    resultado = lint()
    assert resultado["ok"] is True
    assert [f for f in resultado["findings"]
            if f["code"] == "epistemic.mechanism_promised"] == []


def test_contrato_temporal_declara_a_semantica_PINADA_do_valid_at():
    """A regra que o P-9 fixou e que nenhum contrato dizia: página SEM
    `valid_at` é válida em qualquer `as_of` — não é "sem informação",
    é "nenhuma alegação temporal foi feita". Um contrato que omitisse
    isso deixaria o leitor supor filtro onde há passagem livre."""
    registry, _ = load_registry()
    c = registry.get("temporal_partition")
    texto = " ".join(b.text for b in (*c.inductive_biases, *c.assumptions,
                                      *c.known_failure_modes)).lower()
    assert "sem `valid_at`" in texto or "sem valid_at" in texto
    assert "qualquer" in texto


def test_contrato_temporal_distingue_DESPRIORIZAR_de_filtrar():
    """Dois comportamentos no mesmo código, e confundi-los é erro de
    leitura caro: com `as_of` a partição REORDENA (o inválido desce, não
    some); sem `as_of`, supersedida é filtro DURO (INV-003)."""
    registry, _ = load_registry()
    c = registry.get("temporal_partition")
    texto = " ".join(x.text for x in (*c.inductive_biases,
                                      *c.validity_scope)).lower()
    assert "reordena" in texto or "despriorizada" in texto
    assert "inv-003" in texto or "duro" in texto


def test_contrato_de_co_mencao_cruza_os_limites_REAIS_do_codigo():
    """O teto anti-hub (2..30 páginas) e o peso (0.25) são o mecanismo
    inteiro: sem o teto, uma entidade onipresente ligaria tudo com tudo.
    Falsificável: mude a faixa no SQL sem mexer no TOML."""
    import inspect
    from corpusmith.usecases import detect_communities
    registry, _ = load_registry()
    p = dict(registry.get("inferred_cooccurrence_edges").parameters)
    src = inspect.getsource(detect_communities)
    assert (f"BETWEEN {int(p['min_paginas'])} AND {int(p['max_paginas'])}"
            in src)
    assert float(p["peso_da_aresta"]) == (
        detect_communities.W["inferred"] * 0.5)


def test_mecanismos_de_projecao_declaram_o_efeito_da_C6():
    """Os contratos novos nascem com o campo que a C6 criou — quem
    escreve projeção diz que escreve."""
    from corpusmith.epistemic import SideEffect
    registry, _ = load_registry()
    assert SideEffect.PROJECTION_WRITE in registry.get(
        "inferred_cooccurrence_edges").side_effects
    assert registry.get("temporal_partition").side_effects == (
        SideEffect.NONE,)


# ========================================================= ontologia
def test_vocabularios_fechados_sao_registro_separado_dos_EIXOS():
    """Eixo é pergunta sobre uma AFIRMAÇÃO; estes vocabulários são sobre
    outros objetos (relação entre páginas, mecanismo). Misturá-los num
    dicionário só seria o erro de nível que a RFC-004 combate — a
    separação é o ponto, e o `applies_to` de cada um a declara."""
    assert set(onto.AXES) == {"derivation_method", "resolution_status",
                              "governance_status"}
    assert set(onto.VOCABULARIES) == {"semantic_relation", "side_effect"}
    for nome, (valores, objeto, _) in onto.VOCABULARIES.items():
        assert valores and objeto in ("relation", "mechanism"), nome


def test_vocabulario_fechado_espelha_a_constante_real():
    from corpusmith.epistemic import SideEffect
    from corpusmith.kernel.semantics import RELACOES
    valores_rel, _, _ = onto.VOCABULARIES["semantic_relation"]
    valores_efeito, _, _ = onto.VOCABULARIES["side_effect"]
    assert set(valores_rel) == set(RELACOES)
    assert set(valores_efeito) == {e.value for e in SideEffect}


def test_lint_COBRA_verbete_para_vocabulario_fechado(tmp_path):
    """A regra nova, e a que fecha o buraco medido: vocabulário fechado
    sem verbete no `ontology.toml` é ERRO — o mesmo rigor que os eixos
    já tinham. Sem ela, V5 e C6 criaram vocabulário e o léxico não
    cresceu, em silêncio.

    Falsificável por construção: este teste APAGA o verbete e exige o
    finding."""
    import tomllib
    original = onto_lint.DEFAULT_PATH.read_text()
    data = tomllib.loads(original)
    assert "semantic_relation" in data.get("vocabularies", {})
    mutado = tmp_path / "sem_verbete.toml"
    mutado.write_text(original.replace("[vocabularies.semantic_relation]",
                                       "[vocabularies.ignorado_z]"))
    _, findings = onto_lint.lint(mutado)
    assert [f for f in findings
            if f.code == "ontology.vocabulary_undeclared"
            and f.mechanism_id == "semantic_relation"]


def test_lint_recusa_vocabulario_que_MENTE_sobre_o_codigo(tmp_path):
    """Declarar valor que o código não tem é o mesmo defeito do
    `axis_mismatch` — e agora tem o mesmo desfecho."""
    original = onto_lint.DEFAULT_PATH.read_text()
    mutado = tmp_path / "mente.toml"
    mutado.write_text(original.replace(
        'values = ["applies_to", "exemplifies", "refines"]',
        'values = ["applies_to", "exemplifies", "refines", "inventada"]'))
    _, findings = onto_lint.lint(mutado)
    assert [f for f in findings
            if f.code == "ontology.vocabulary_mismatch"]


def test_o_registro_real_passa_no_lint_reforcado():
    data, findings = onto_lint.lint()
    assert [f for f in findings if f.severity == "error"] == []
    assert set(data["vocabularies"]) == set(onto.VOCABULARIES)


def test_o_lexico_cresceu_com_as_palavras_QUE_O_PRODUTO_USA():
    """As palavras que esta trilha pôs na boca do produto entram no
    léxico com raiz e fronteira. Verbete sem `constrains` é ornamento:
    a raiz só serve se PROIBIR alguma coisa."""
    data, _ = onto_lint.lint()
    termos = data["terms"]
    for novo in ("stability", "difficulty", "application", "side_effect"):
        assert novo in termos, novo
        assert termos[novo]["constrains"], novo
        assert termos[novo]["roots"], novo   # o campo dos termos


def test_deriva_da_autoridade_segue_aberta_e_agora_com_medicao():
    """A V2 NÃO resolveu a deriva de `authority` (cinco sentidos) — ela
    contornou, pondo o sentido no canônico. Fechar a deriva aqui seria
    alegar mais do que se fez; o registro ganha a MEDIÇÃO e mantém o
    status aberto."""
    data, _ = onto_lint.lint()
    deriva = data["drift"]["authority"]
    assert deriva["status"] == "open"
    assert "V2" in " ".join(str(v) for v in deriva.values())
