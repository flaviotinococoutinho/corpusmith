"""F4-PR3c — o resíduo do P-9 sai do bundle, em lote e com preview.

ADR-52 decisão 1 tirou o default de escrita (`base._document` não carimba
mais `valid_at = now`), mas deixou dito o que NÃO fez: *"o legado de
`valid_at` (~toda página de máquina existente) fica INALTERADO até o ato em
lote da F4-PR3 — reescrever frontmatter em massa sem preview seria
exatamente o que o produto proíbe"*.

**Por que este pacote não precisa de contrato epistêmico.** A assinatura da
corrupção é IGUALDADE, não limiar: página de máquina cujo `valid_at` é
exatamente o `timestamp` (`base._document` usava o MESMO objeto `now` nos
dois campos). Não há nada a calibrar — ao contrário do `factual_conflict`,
que carrega um número escolhido e por isso declara garantia relativa.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from corpusmith.kernel.curation import valid_at_e_legado
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.usecases.curate import ACTS, ClearLegacyValidAt

AGORA = datetime(2024, 3, 1, 12, 0, tzinfo=timezone.utc)


def _doc(rel, title, **meta):
    meta.setdefault("generated_via", "local:promote")
    if str(meta["generated_via"]).startswith(("api:", "local:")):
        meta.setdefault("source_sha256", "0" * 64)
    return OKFDocument(rel_path=rel, body=f"# {title}\n\nprosa.",
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only", **meta))


def _escreve(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _valid_at(kb, rel):
    return BundleReader(kb / "bundle").load(rel) \
        .meta.model_dump(exclude_none=True).get("valid_at")


# ================================================ a regra pura (kernel)
def test_a_assinatura_do_p9_e_igualdade_exata_em_pagina_de_maquina():
    """Não é heurística: é o mesmo objeto `now` nos dois campos.

    Falsificável: trocando a igualdade por uma janela (`< 1s`), o terceiro
    caso — carimbo humano com 1 segundo de diferença — passa a ser tratado
    como legado e a asserção reprova."""
    maquina = {"generated_via": "local:promote",
               "valid_at": AGORA, "timestamp": AGORA}
    assert valid_at_e_legado(maquina) is True

    # página HUMANA com os carimbos iguais NÃO é legado: `valid_at` humano
    # vem de um ato com `when` declarado, e coincidir com a escrita é
    # possível e legítimo — o default automático só existia no eixo máquina
    humana = {**maquina, "generated_via": "human:promote"}
    assert valid_at_e_legado(humana) is False

    # alegação DE VERDADE sobre o mundo: datas diferentes, fica
    real = {**maquina, "valid_at": AGORA - timedelta(days=365)}
    assert valid_at_e_legado(real) is False

    # sem `valid_at` não há o que limpar
    assert valid_at_e_legado({"generated_via": "local:promote",
                              "timestamp": AGORA}) is False


# ============================================== o ato: preview e efeito
@pytest.fixture
def sujo(settings, kb):
    """Duas páginas de máquina com o carimbo colapsado, uma com alegação
    real, e uma humana com os carimbos iguais (que NÃO pode ser tocada)."""
    _escreve(settings, kb,
             _doc("concepts/m1.md", "M1", valid_at=AGORA, timestamp=AGORA),
             _doc("concepts/m2.md", "M2", valid_at=AGORA, timestamp=AGORA),
             _doc("concepts/real.md", "Real", timestamp=AGORA,
                  valid_at=AGORA - timedelta(days=365)),
             _doc("concepts/h.md", "H", generated_via="human:promote",
                  valid_at=AGORA, timestamp=AGORA))
    return settings


def test_preview_e_puro_e_nao_escreve_nada(sujo, kb):
    """O preview é o INSTRUMENTO DE MEDIDA: é ele que responde quantas
    páginas estão sujas no corpus do usuário, sem tocar em nada. Sem isso o
    ato seria inaplicável — não há corpus real neste repositório para
    dimensionar o estrago, e não precisa haver.

    Falsificável: se `_plan` escrevesse, `valid_at` sumiria aqui."""
    out = ClearLegacyValidAt(sujo).execute(dry_run=True)
    assert out["applied"] is False
    preview = out["preview"]
    assert preview["pages"] == ["concepts/m1.md", "concepts/m2.md"]
    # nada mudou no canônico
    assert _valid_at(kb, "concepts/m1.md") == AGORA


def test_o_ato_remove_so_o_carimbo_colapsado(sujo, kb):
    """E deixa em paz a alegação verdadeira e a página humana.

    Falsificável: removendo a guarda `generated_via` de `valid_at_e_legado`,
    `concepts/h.md` perde o `valid_at` e a última asserção reprova."""
    ClearLegacyValidAt(sujo).execute()
    assert _valid_at(kb, "concepts/m1.md") is None
    assert _valid_at(kb, "concepts/m2.md") is None
    # alegação real sobre o mundo: intocada
    assert _valid_at(kb, "concepts/real.md") == AGORA - timedelta(days=365)
    # página humana: intocada, mesmo com os carimbos iguais
    assert _valid_at(kb, "concepts/h.md") == AGORA


def test_a_nota_declara_que_remove_e_nao_recupera(sujo):
    """O ato apaga uma alegação FALSA; não recupera a verdadeira — isso
    exigiria a fonte. Apresentar-se como "conserta o valid_at legado" seria
    vender o que não se entrega.

    E declara a mudança de comportamento no `/ask`, que é o OBJETIVO do
    ato: hoje estas páginas são rebaixadas em qualquer consulta com `as_of`
    anterior à data de escrita, re-ranqueadas por um carimbo sem
    significado.

    Falsificável: encurtando a nota para só "N páginas limpas", as três
    asserções reprovam."""
    nota = ClearLegacyValidAt(sujo).execute(dry_run=True)["preview"]["note"]
    assert "REMOVE" in nota and "não recupera" in nota
    assert "as_of" in nota and "/ask" in nota
    assert "undo" in nota


def test_o_lote_tem_teto_declarado_e_o_preview_diz_quantas_ficaram(
        settings, kb):
    """`~toda página de máquina existente` pode ser milhares, e um preview
    com milhares de diffs torna a garantia central do eixo humano NOMINAL:
    ninguém lê 3.000 diffs, e "preview obrigatório" vira teatro.

    Falsificável: sem o fatiamento por `_limit`, o preview traz as cinco
    páginas e a asserção de comprimento reprova."""
    _escreve(settings, kb, *[
        _doc(f"concepts/m{i}.md", f"M{i}", valid_at=AGORA, timestamp=AGORA)
        for i in range(5)])
    preview = ClearLegacyValidAt(settings, limit=2) \
        .execute(dry_run=True)["preview"]
    assert len(preview["pages"]) == 2
    assert "TETO DO LOTE" in preview["note"]
    assert "3 página(s)" in preview["note"]


def test_bundle_limpo_nao_propoe_nada(settings, kb):
    """Rodar o ato num bundle já limpo não pode inventar trabalho.

    Falsificável: sem o `if not lote`, `_preview_write([])` produziria um
    preview vazio sem nota e a asserção reprova."""
    _escreve(settings, kb, _doc("concepts/ok.md", "Ok", timestamp=AGORA))
    preview = ClearLegacyValidAt(settings).execute(dry_run=True)["preview"]
    assert preview["pages"] == []
    assert "está limpo" in preview["note"]


def test_o_ato_entra_no_registro_fechado_e_ganha_undo(sujo, kb):
    """`ACTS` é a tabela fechada que facade, API e CLI resolvem: entrar nela
    é o que dá endpoint, CLI e `curation_acts` de graça (docstring de
    `curate/__init__`). E o undo do eixo humano reconstrói do commit pai —
    A-2: aposentar não é apagar, e desfazer ESCREVE um ato inverso.

    Falsificável: tirando a entrada de `ACTS`, a primeira asserção reprova;
    o undo verifica que a remoção em lote é reversível de verdade."""
    from corpusmith.usecases.curate import UndoCurationAct
    assert ACTS["clear_legacy_valid_at"] is ClearLegacyValidAt
    out = ClearLegacyValidAt(sujo).execute()
    assert _valid_at(kb, "concepts/m1.md") is None
    UndoCurationAct(sujo, act_id=out["id"]).execute()
    # o carimbo VOLTA — o ato em lote é reversível como qualquer outro
    assert _valid_at(kb, "concepts/m1.md") == AGORA
    assert _valid_at(kb, "concepts/m2.md") == AGORA


# ============================ os defeitos que o QA adversarial encontrou
def test_folga_de_relogio_nao_pode_apagar_valid_at_verdadeiro(settings, kb):
    """`TOLERANCIA_COLAPSO = timedelta(0)` estava DECLARADA e INGUARDADA.

    Medido pelo QA: a suíte inteira ficava verde com a janela em `seconds=1`,
    `minutes=5`, `hours=1`, `days=1`, `days=30` — só reprovava a partir de
    `days=365`, porque a única fixture de "alegação real" estava a um ano do
    `timestamp`. O erro plausível (alguém acrescentar folga de relógio
    "porque os carimbos podem não bater exatamente") passava inteiro, e o
    efeito é apagar `valid_at` VERDADEIRO — a coisa que a constante existe
    para impedir.

    Esta fixture põe a alegação real a UM SEGUNDO do timestamp: qualquer
    folga não-zero a destrói.

    Falsificável: `TOLERANCIA_COLAPSO = timedelta(seconds=1)` reprova."""
    quase = AGORA - timedelta(seconds=1)
    _escreve(settings, kb,
             _doc("concepts/quase.md", "Quase", timestamp=AGORA,
                  valid_at=quase))
    assert valid_at_e_legado({"generated_via": "local:promote",
                              "timestamp": AGORA, "valid_at": quase}) is False
    ClearLegacyValidAt(settings).execute()
    assert _valid_at(kb, "concepts/quase.md") == quase, (
        "um segundo de diferença é ALEGAÇÃO, não colapso: `base._document` "
        "usava o MESMO objeto `now` nos dois campos, então o legado é "
        "igualdade EXATA")


def test_o_teto_de_lote_default_e_ele_proprio_uma_garantia(settings, kb):
    """`LOTE_MAXIMO = 50` estava INGUARDADO: o único teste passava
    `limit=2` explícito, exercitando o parâmetro e nunca o default.

    Medido pelo QA: `LOTE_MAXIMO = 100000` deixava a suíte inteira verde —
    e o commit dedica uma decisão inteira a sustentar que o teto é a
    garantia central do eixo humano ("preview que ninguém consegue ler não
    é preview"). Uma garantia que some sem quebrar nada não é garantia.

    Falsificável: subir `LOTE_MAXIMO` reprova a primeira asserção; descer
    para 1 reprova a segunda."""
    _escreve(settings, kb, *[
        _doc(f"concepts/m{i:03d}.md", f"M{i}", valid_at=AGORA,
             timestamp=AGORA) for i in range(60)])
    preview = ClearLegacyValidAt(settings).execute(dry_run=True)["preview"]
    assert len(preview["pages"]) == 50, (
        "o default tem de ser legível por um humano: 60 sujas, 50 no lote")
    assert "10 página(s)" in preview["note"]
    # e o teto é TETO: pedir mais não o levanta
    grande = ClearLegacyValidAt(settings, limit=10_000) \
        .execute(dry_run=True)["preview"]
    assert len(grande["pages"]) == 50
