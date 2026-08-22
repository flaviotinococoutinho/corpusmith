"""RFC-006 V1 — normas (ISO, NBR, RFC, circulares…) como sujeitos fortes.

O material de quem estuda padrões é o documento normativo, e ele identifica
tão fortemente quanto um DOI. Este pacote promove os subkinds de `standard`
a sujeitos de `contradiction_candidate`/`factual_conflict` — a MESMA
maquinaria, o MESMO refinamento da RFC-005, nenhum detector paralelo.

Duas fronteiras deliberadas, ambas testadas aqui:

- `regulator` (LGPD, OWASP…) fica FORA: nomeia um referente, não um
  documento — incluí-lo compraria o sujeito inventado que a RFC-005 §3
  recusou;
- a RECONCILIAÇÃO não muda: `STRONG_IDS` é constante própria
  (`reconcile_candidate.py`), e duas notas que citam a mesma ISO NÃO podem
  virar "o mesmo documento" na escada de escrita.
"""
from __future__ import annotations
import pytest
from corpusmith.harness.local_policy import CONTRADICTION_IDS, check_corpus
from corpusmith.normalize.detectors.standards import detect
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.usecases.reconcile_candidate import STRONG_IDS


def _doc(rel, title, body, **extra):
    extra.setdefault("generated_via", "human:promote")
    if str(extra["generated_via"]).startswith(("api:", "local:")):
        extra.setdefault("source_sha256", "0" * 64)
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only", **extra))


def _escreve(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _findings(kb, regra=None):
    reader = BundleReader(kb / "bundle")
    out = check_corpus(list(reader.iter_concepts()), reader)
    return [f for f in out if regra is None or f.rule == regra]


# ================================================ o detector de circulares
def test_circular_normativa_e_detectada_e_adjetivo_nao():
    """Precisão > recall: "circular" é adjetivo comum em pt-BR, e o
    detector exige C maiúsculo E (ponto de milhar OU marcador nº).

    Falsificável: relaxar qualquer uma das duas exigências faz as linhas
    negativas reprovarem."""
    achados = {m.canonical: m.subkind
               for m in detect("A Circular 3.978/2020 e a Circular nº 979 "
                               "regem o tema.")}
    assert achados == {"Circular 3.978/2020": "circular",
                       "Circular 979": "circular"}

    assert detect("Evite referência circular no grafo.") == []
    assert detect("O plano Economia Circular 2030 foi lançado.") == []
    assert detect("a circular interna 12 do RH") == []


# ==================================== normas formam sujeito de contradição
def test_duas_paginas_da_mesma_norma_sem_sucessao_viram_candidato(
        settings, kb):
    """O caso de quem estuda padrões: duas notas sobre a MESMA ISO,
    nenhuma relação de sucessão — coexistência que merece a fila.

    Medido ANTES da mudança: `check_corpus` devolvia lista vazia, porque o
    filtro só aceitava `kind == "identifier"` e norma é `kind="standard"`.
    Falsificável: restaurar aquele filtro zera os findings deste teste."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "Nota A",
                  "# Nota A\n\nA ISO 27001:2022 trata de gestão."),
             _doc("concepts/b.md", "Nota B",
                  "# Nota B\n\nA ISO 27001:2022 exige inventário."))
    f = _findings(kb, "policy.contradiction_candidate")
    assert len(f) == 1
    assert f[0].meta["identifier"] == "ISO 27001:2022"


def test_divergencia_numerica_sob_a_mesma_norma_e_conflito_factual(
        settings, kb):
    """O refinamento da RFC-005 herdado sem código novo: mesma RFC citada,
    8 MB contra 4 MB — conflito factual, com o mesmo formato de meta."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "Nota A",
                  "# Nota A\n\nA RFC 9110 fixa o limite em 8 MB."),
             _doc("concepts/b.md", "Nota B",
                  "# Nota B\n\nA RFC 9110 fixa o limite em 4 MB."))
    regras = [f.rule for f in _findings(kb)]
    assert regras == ["policy.contradiction_candidate",
                      "policy.factual_conflict"]
    f = _findings(kb, "policy.factual_conflict")[0]
    assert f.meta["identifier"] == "RFC 9110"
    assert sorted(f.meta["pages"]) == ["concepts/a.md", "concepts/b.md"]


def test_regulator_nao_forma_sujeito(settings, kb):
    """LGPD nomeia a LEI, não um texto específico — duas páginas que a
    mencionam com números diferentes não são conflito sobre "o mesmo
    documento". Falsificável: acrescentar "regulator" em
    CONTRADICTION_IDS faz este teste reprovar."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "Nota A",
                  "# Nota A\n\nA LGPD prevê multa de 50 MB de logs."),
             _doc("concepts/b.md", "Nota B",
                  "# Nota B\n\nA LGPD prevê retenção de 20 MB de logs."))
    assert _findings(kb) == []
    assert "regulator" not in CONTRADICTION_IDS


def test_versao_de_norma_e_sujeito_distinto(settings, kb):
    """`ISO 9001` e `ISO 9001:2015` têm canônicos diferentes e NÃO
    agrupam — no regime normativo a edição muda o texto. O contrato
    declara o custo (citar com e sem ano esconde o conflito); este teste
    prende o comportamento para que o custo seja o DECLARADO."""
    _escreve(settings, kb,
             _doc("concepts/a.md", "Nota A",
                  "# Nota A\n\nA ISO 9001 pede 8 MB de registros."),
             _doc("concepts/b.md", "Nota B",
                  "# Nota B\n\nA ISO 9001:2015 pede 4 MB de registros."))
    assert _findings(kb) == []


# ======================================= as fronteiras que NÃO se movem
def test_reconciliacao_nao_ganha_normas_por_efeito_colateral():
    """A escada de escrita decide "é o mesmo documento?" — e duas notas
    que citam a mesma ISO NÃO são o mesmo documento. `STRONG_IDS` é
    constante própria e este teste congela a separação: quem quiser
    normas na reconciliação precisa passar por RFC, não por carona."""
    assert set(STRONG_IDS) == {"doi", "isbn", "issn", "arxiv", "git_sha"}
    assert "iso" not in STRONG_IDS and "rfc" not in STRONG_IDS


def test_o_contrato_declara_o_sujeito_ampliado():
    """O `subject_identifiers` do contrato é cruzado com o código em
    test_epistemics_toml; aqui prende-se a DECISÃO: acadêmicos + normas,
    sem regulator."""
    assert set(CONTRADICTION_IDS) == {
        "doi", "isbn", "issn", "arxiv",
        "iso", "nbr", "rfc", "nist", "ieee", "eu_reg", "circular"}
