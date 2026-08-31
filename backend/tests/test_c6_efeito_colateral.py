"""C6 — o contrato passa a ter ONDE declarar que o mecanismo ESCREVE.

O achado que gerou este item (`docs/17` §C6) foi medido no produto: com
`memory.auto_recycle` ligado, um `POST /ask` — leitura no modelo mental
do usuário e no próprio contrato de abstenção — reidratava uma página,
escrevia no bundle e **movia o HEAD do Git**. O agravante estrutural: o
dataclass `EpistemicContract` não tinha NENHUM campo de efeito
colateral, então nenhuma regra de lint poderia pegar isso. A lacuna era
geradora — não dava para declarar o defeito no lugar onde o produto
declara o que sabe sobre si.

Este pacote fecha a lacuna com três guardas, e a terceira é a que
impede a declaração de virar decoração: o efeito declarado é CRUZADO com
o código dos `implementation_refs`.
"""
from __future__ import annotations

import pytest

from corpusmith.epistemic import SideEffect, parse_registry, validate_registry
from corpusmith.harness.epistemics import load_registry

_BASE = """
schema_version = 1
[registry]
version = "1.0.0"
[mechanisms.m1]
title = "t"
decision = "d"
implementation_refs = ["backend/pyproject.toml"]
inductive_biases = ["um viés"]
validity_scope = ["um escopo"]
known_failure_modes = ["um modo de falha"]
guarantee_kind = "heuristic"
guarantee_relative_to = "algo observável"
evidence = ["deterministic_check"]
"""


def _codigos(texto: str) -> set[str]:
    registry, parse_findings = parse_registry(texto)
    return {f.code for f in (*parse_findings,
                             *validate_registry(registry))}


# ------------------------------------------------------- o vocabulário
def test_efeitos_sao_vocabulario_fechado():
    assert {e.value for e in SideEffect} == {
        "none", "canonical_write", "projection_write", "state_write"}


def test_efeito_invalido_e_recusado_como_qualquer_vocabulario():
    assert "epistemic.invalid_vocabulary" in _codigos(
        _BASE + '\nside_effects = ["apaga_tudo"]\n')


def test_ausencia_do_campo_continua_valendo():
    """Campo NOVO não pode invalidar os 25 contratos existentes — a
    ausência significa "não declarado", e a leitura honesta disso é o
    default vazio, não um erro retroativo."""
    registry, _ = parse_registry(_BASE)
    assert registry.contracts[0].side_effects == ()
    assert "epistemic.invalid_vocabulary" not in _codigos(_BASE)


# -------------------------------------------------------- a regra nova
def test_escrita_no_canonico_exige_alto_impacto():
    """Escrever no canônico É alto impacto neste produto: o bundle é a
    autoridade e o commit é para sempre. Declarar a escrita e negar o
    impacto seria a contradição que o registro existe para tornar
    impossível de esconder."""
    codigos = _codigos(_BASE + '\nside_effects = ["canonical_write"]\n'
                               'high_impact = false\n')
    assert "epistemic.canonical_write_without_impact" in codigos


def test_escrita_no_canonico_com_alto_impacto_passa():
    codigos = _codigos(_BASE + '\nside_effects = ["canonical_write"]\n'
                               'high_impact = true\n'
                               'fallback = ["request_human_review"]\n')
    assert "epistemic.canonical_write_without_impact" not in codigos


def test_none_com_outro_efeito_e_contradicao():
    """`none` ao lado de qualquer efeito é o contrato dizendo duas coisas
    opostas — e um leitor que veja `none` primeiro lê errado."""
    assert "epistemic.side_effect_contradiction" in _codigos(
        _BASE + '\nside_effects = ["none", "state_write"]\n')


def test_projecao_e_estado_nao_exigem_alto_impacto():
    """Projeção é recomputável e estado de uso não é conhecimento: exigir
    `high_impact` deles diluiria a palavra até ela não significar nada."""
    for efeito in ("projection_write", "state_write"):
        assert "epistemic.canonical_write_without_impact" not in _codigos(
            _BASE + f'\nside_effects = ["{efeito}"]\n')


# ------------------------------- o cruzamento (a declaração vira prova)
def test_nenhum_MODULO_que_escreve_fica_sem_declaracao():
    """A guarda que impede a declaração de virar decoração — e a
    granularidade dela, corrigida por um caso real.

    A primeira versão exigia que TODO mecanismo cujo `implementation_ref`
    importa o `BundleWriter` declarasse `canonical_write`. Parecia certo
    e é um ERRO DE NÍVEL (docs/28 §2): um módulo hospeda vários
    mecanismos com efeitos diferentes. Medido quando
    `inferred_cooccurrence_edges` entrou: ele vive em
    `detect_communities.py` — que escreve páginas de comunidade — mas o
    MECANISMO dele só monta adjacência em memória. A regra antiga
    forçaria uma declaração FALSA para calar o teste, que é o oposto do
    que ela existe para fazer.

    O invariante honesto é por MÓDULO: se um módulo alcança a porta de
    escrita, ALGUÉM entre os mecanismos que o citam tem de declarar
    `canonical_write`. Mais fraco que o anterior — e verdadeiro.

    Falsificável: tire `canonical_write` de `[mechanisms.memory_freeze]`
    (único dono de `cold_memory.py`) e este teste reprova."""
    import ast
    from collections import defaultdict
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]

    def importa_writer(caminho: Path) -> bool:
        """IMPORTAR o writer, não citá-lo: a checagem por substring
        acusava sete mecanismos, e cinco eram menção em comentário."""
        for node in ast.walk(ast.parse(caminho.read_text())):
            nomes = ([a.name for a in node.names]
                     if isinstance(node, (ast.Import, ast.ImportFrom))
                     else [])
            if any("BundleWriter" in n for n in nomes):
                return True
        return False

    registry, _ = load_registry()
    declaram: dict[str, bool] = defaultdict(bool)
    for contrato in registry.contracts:
        escreve = SideEffect.CANONICAL_WRITE in contrato.side_effects
        for ref in contrato.implementation_refs:
            if ref.endswith(".py") and (repo / ref).is_file() \
                    and importa_writer(repo / ref):
                declaram[ref] |= escreve
    mudos = sorted(ref for ref, ok in declaram.items() if not ok)
    assert mudos == [], (
        "módulos que alcançam o BundleWriter e cujos mecanismos NENHUM "
        f"declara `canonical_write`: {mudos}")


def test_o_caso_C6_esta_declarado_no_registro():
    """O achado que gerou o item: a abstenção pode escrever no canônico
    (reidratação por `auto_recycle`) e isso agora está DITO onde o
    produto declara o que sabe sobre si."""
    registry, _ = load_registry()
    abstencao = registry.get("abstention")
    assert SideEffect.CANONICAL_WRITE in abstencao.side_effects
    assert abstencao.high_impact is True


def test_efeitos_viajam_na_serializacao():
    """O painel Qualidade e a API leem daqui — um campo que não viaja é
    um campo que ninguém vê (a lição da R9 da V2)."""
    registry, _ = load_registry()
    d = registry.get("abstention").to_dict()
    assert "canonical_write" in d["side_effects"]
