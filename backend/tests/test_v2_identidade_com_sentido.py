"""RFC-006 V2 — identidade-com-sentido: "entropia (física)" ≠ "entropia
(informação)".

O coração do pedido sobre ÓTICAS. Até aqui um alias resolvia para
exatamente UM canônico e a colisão era decidida por ordem de inserção
(`self.map[f] = ...`, o último a escrever vencia em silêncio): dois
sentidos vizinhos colapsavam na mesma entidade, ligavam páginas que não
falam da mesma coisa, e ninguém era avisado.

A correção não inventa mecanismo — usa o que o produto já tem para NÃO
decidir. `confidence="ambiguous"` já significa "não resolvido" em toda a
cadeia (`_rewritable` não reescreve, `fts` não indexa, o frontmatter não
lista, o grafo pesa 0.15). O que faltava era PRODUZIR a ambiguidade.

**Precedência ≠ ambiguidade**: seed e `reference.db` são defaults, o
bundle é curadoria — a curadoria vence e isso NÃO é conflito. Conflito é
quando dois registros da MESMA camada disputam o alias.
"""
from __future__ import annotations
import pytest
from corpusmith.harness.local_policy import check_corpus
from corpusmith.normalize import Gazetteer, analyze, rewrite
from corpusmith.normalize.gazetteer import (TIER_BUNDLE, TIER_REFERENCIA,
                                            base, sentido)
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import _gazetteer_fingerprint, rebuild_index
from corpusmith.runtime.db import connect


def _doc(rel, title, body="", **extra):
    extra.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body or f"# {title}\n\nprosa.",
                       meta=OKFFrontMatter(type=extra.pop("type", "concept"),
                                           title=title, privacy="local_only",
                                           **extra))


def _registro(rel, canonical, aliases, authority="term"):
    return _doc(rel, canonical, type="authority_record",
                canonical=canonical, aliases=aliases, authority=authority)


def _escreve(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _findings(kb, regra=None):
    reader = BundleReader(kb / "bundle")
    out = check_corpus(list(reader.iter_concepts()), reader)
    return [f for f in out if regra is None or f.rule == regra]


@pytest.fixture
def entropia(settings, kb):
    """Os DOIS sentidos curados, e uma página que usa o alias nu."""
    _escreve(settings, kb,
             _registro("authorities/term/entropia-fisica.md",
                       "Entropia (física)", ["entropia"]),
             _registro("authorities/term/entropia-info.md",
                       "Entropia (informação)", ["entropia"]),
             _doc("concepts/estudo.md", "Estudo",
                  "# Estudo\n\nA entropia cresce em sistemas fechados."))
    return settings


# ============================================== o qualificador (puro)
def test_sentido_e_base_leem_o_qualificador_do_canonico():
    """O sentido mora no CANÔNICO — campo `sense` paralelo criaria dois
    donos do mesmo fato, e o campo `authority` já carrega cinco sentidos
    (`[drift.authority]`, ABERTA). Parse conservador: só um parêntese
    FINAL, sem aninhamento."""
    assert sentido("Entropia (física)") == "física"
    assert base("Entropia (física)") == "Entropia"
    assert sentido("PostgreSQL") is None
    assert base("PostgreSQL") == "PostgreSQL"
    assert sentido("OAuth 2.0") is None          # ponto não é parêntese
    assert sentido("Node.js") is None


# ================================= o alias disputado vira AMBÍGUO
def test_alias_disputado_por_dois_registros_nao_resolve_para_nenhum(
        entropia, kb):
    """O caso central. Medido ANTES da mudança: `analyze` devolvia UM
    match resolvido — o último registro inserido —, e "entropia" da física
    virava a entidade da informação (ou o contrário) conforme a ordem de
    leitura do bundle.

    Falsificável: restaure `self.map[f] = cand` (último vence) e este
    teste reprova em `confidence`, porque volta a existir um vencedor."""
    reader = BundleReader(kb / "bundle")
    from corpusmith.okf.authorities import load_gazetteer
    gaz = load_gazetteer(reader)

    matches = [m for m in analyze("A entropia cresce.", gaz=gaz).matches
               if m.kind == "entity"]
    assert len(matches) == 1
    m = matches[0]
    assert m.confidence == "ambiguous"
    # o canônico continua sendo a SUPERFÍCIE: o produto não escolhe um
    # lado no texto de ninguém
    assert m.canonical == m.surface == "entropia"
    assert m.data["candidates"] == ["Entropia (física)",
                                    "Entropia (informação)"]
    assert m.data["senses"] == ["física", "informação"]


def test_a_forma_qualificada_resolve_normalmente(entropia, kb):
    """A saída do curador: escrever o canônico completo desambigua na
    hora — e é por isso que o sentido mora NO canônico."""
    from corpusmith.okf.authorities import load_gazetteer
    gaz = load_gazetteer(BundleReader(kb / "bundle"))
    m = [x for x in analyze("A Entropia (física) cresce.", gaz=gaz).matches
         if x.kind == "entity"][0]
    assert m.confidence == "extracted"
    assert m.canonical == "Entropia (física)"


def test_ambiguo_nao_e_reescrito_no_texto(entropia, kb):
    """A guarda mais importante do pacote. `rewrite` roda em TODA página
    de máquina; se um match ambíguo fosse reescrivível, o compilador
    escolheria um sentido no corpo do usuário — em silêncio e por
    construção. `_rewritable` exige `extracted`, e este teste prende isso.

    Falsificável: troque a marca para `extracted` no `detect` ambíguo e o
    corpo sai reescrito com um dos dois sentidos."""
    from corpusmith.okf.authorities import load_gazetteer
    gaz = load_gazetteer(BundleReader(kb / "bundle"))
    texto = "A entropia cresce."
    assert rewrite(texto, analyze(texto, gaz=gaz)) == texto


def test_ambiguo_nao_entra_no_indice_de_entidades_nem_no_frontmatter(
        entropia, kb, settings):
    """Não indexar é o que impede o alias disputado de LIGAR páginas que
    não falam da mesma coisa — o dano real do colapso silencioso."""
    idx = connect(settings.app_support / "index.db")
    try:
        canonicos = {r["canonical"] for r in idx.execute(
            "SELECT e.canonical FROM entities e JOIN page_entities pe "
            "ON pe.entity_id = e.id WHERE pe.page = 'concepts/estudo.md'")}
    finally:
        idx.close()
    assert "Entropia (física)" not in canonicos
    assert "Entropia (informação)" not in canonicos

    from corpusmith.okf.authorities import load_gazetteer
    gaz = load_gazetteer(BundleReader(kb / "bundle"))
    rep = analyze("A entropia cresce.", gaz=gaz)
    assert rep.entities_frontmatter() == []


# ===================================== precedência NÃO é ambiguidade
def test_registro_curado_vence_o_seed_sem_virar_conflito(settings, kb):
    """Regressão que a V2 poderia introduzir: a curadoria sempre venceu os
    seeds embutidos (v0.22), e transformar isso em "conflito" encheria de
    aviso todo bundle que corrige uma grafia.

    Falsificável: remova a resolução por camada (`teto`) e o alias `sqlite`
    passa a ser reportado como conflito."""
    _escreve(settings, kb,
             _registro("authorities/stack/sqlite.md", "SQLite (banco)",
                       ["sqlite"], authority="stack"))
    from corpusmith.okf.authorities import load_gazetteer
    gaz = load_gazetteer(BundleReader(kb / "bundle"))
    assert gaz.conflitos() == {}
    m = [x for x in analyze("uso sqlite aqui", gaz=gaz).matches
         if x.kind == "entity"][0]
    assert (m.canonical, m.confidence) == ("SQLite (banco)", "extracted")


def test_camadas_diferentes_resolvem_por_precedencia():
    """Bundle > reference.db > seed, direto no gazetteer — sem passar por
    disco. O mesmo alias em camadas diferentes tem UM dono."""
    gaz = Gazetteer([("Alfa", ["x"], "term", None)], curados=[
        {"canonical": "Beta", "aliases": ["x"], "tier": TIER_REFERENCIA},
        {"canonical": "Gama", "aliases": ["x"], "tier": TIER_BUNDLE}])
    assert [c.canonical for c in gaz.candidatos("x")] == ["Gama"]
    assert gaz.conflitos() == {}


def test_mesmo_canonico_repetido_nao_e_conflito():
    """Dois registros que dizem a MESMA coisa são o mesmo fato dito duas
    vezes — dedup, não disputa."""
    gaz = Gazetteer([], curados=[
        {"canonical": "Entropia (física)", "aliases": ["entropia"],
         "page": "a.md"},
        {"canonical": "Entropia (física)", "aliases": ["entropia"],
         "page": "b.md"}])
    assert gaz.conflitos() == {}


# ============================================= o finding e o seu ato
def test_alias_conflict_nomeia_o_ato_e_as_paginas_de_uso(entropia, kb):
    """O finding não diz só "há conflito": diz QUAL edição resolve. Com os
    sentidos já declarados, o que sobra é o alias nu servindo a dois donos.

    Falsificável: sem `_alias_conflitantes` em `check_corpus`, zero
    findings; sem as páginas de uso, a asserção de `pages` reprova."""
    f = _findings(kb, "policy.alias_conflict")
    assert len(f) == 1
    assert f[0].severity == "warn"            # check_corpus NUNCA é error
    assert f[0].path.startswith("authorities/")   # alvo é o registro editável
    assert f[0].meta["alias"] == "entropia"
    assert f[0].meta["candidates"] == ["Entropia (física)",
                                       "Entropia (informação)"]
    assert f[0].meta["pages"] == ["concepts/estudo.md"]
    assert "tire-o de um dos registros" in f[0].message


def test_sem_qualificador_o_finding_pede_o_sentido(settings, kb):
    """Diagnóstico diferente, ato diferente: canônicos SEM sentido pedem
    que o sentido seja declarado, não que o alias saia."""
    _escreve(settings, kb,
             _registro("authorities/term/a.md", "Entropia", ["entropia"]),
             _registro("authorities/term/b.md", "Entropia de Shannon",
                       ["entropia"]))
    f = _findings(kb, "policy.alias_conflict")
    assert len(f) == 1
    assert "declare o sentido no canônico" in f[0].message
    # o REGISTRO menciona o termo que define, por construção — contá-lo
    # como "uso" faria o finding apontar de volta para si mesmo. Definição
    # não é uso. Falsificável: tire o filtro de `authority_record` em
    # `check_corpus` e as duas páginas de registro aparecem aqui
    assert f[0].meta["pages"] == []           # ninguém USA o alias ainda


def test_bundle_sem_registro_duplicado_nao_gera_finding(settings, kb):
    """Ausência de conflito é o caso comum — e o detector só vê o que
    alguém CUROU: um bundle sem authority_record tem zero conflitos e
    vocabulário inteiramente por resolver (limite declarado no contrato)."""
    _escreve(settings, kb, _doc("concepts/x.md", "X",
                                "# X\n\nA entropia cresce."))
    assert _findings(kb, "policy.alias_conflict") == []


# ================================== o índice não pode ficar obsoleto
def test_fingerprint_muda_quando_o_conflito_aparece():
    """O carimbo do gazetteer decide se o índice é reconstruído. Guardando
    só o primeiro candidato, introduzir (ou resolver) um conflito passaria
    despercebido e o índice continuaria servindo a entidade que o
    gazetteer já não resolve — obsolescência silenciosa exatamente onde
    este carimbo existe para não haver.

    Os dois gazetteers têm o MESMO conjunto de aliases de propósito: só o
    número de candidatos de `entropia` muda. Sem isso o teste seria
    teatro — passaria pela chave a mais, não pelo payload (medido: a
    primeira versão deste teste sobreviveu à mutação por esse motivo)."""
    comuns = [{"canonical": "Entropia (física)", "aliases": ["entropia"]}]
    resolvido = Gazetteer([], curados=comuns + [
        {"canonical": "Entropia (informação)", "aliases": []}])
    disputado = Gazetteer([], curados=comuns + [
        {"canonical": "Entropia (informação)", "aliases": ["entropia"]}])
    assert set(resolvido.map) == set(disputado.map), \
        "as duas fixtures precisam diferir SÓ no número de candidatos"
    assert _gazetteer_fingerprint(resolvido) \
        != _gazetteer_fingerprint(disputado)


def test_termos_conta_identidades_distintas():
    """O painel conta IDENTIDADES, não entradas de alias — e um alias
    disputado contribui com as duas."""
    gaz = Gazetteer([], curados=[
        {"canonical": "Entropia (física)", "aliases": ["entropia", "s"]},
        {"canonical": "Entropia (informação)", "aliases": ["entropia"]}])
    assert {c for c, _a, _q in gaz.termos()} == {"Entropia (física)",
                                                 "Entropia (informação)"}
