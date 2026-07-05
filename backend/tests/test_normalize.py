"""Golden tests permanentes do pacote normalize (v0.8 §12.1)."""
from __future__ import annotations
from llmwiki.normalize import Gazetteer, analyze, rewrite
from llmwiki.normalize.detectors.dates import detect as detect_dates
from llmwiki.normalize.detectors.identifiers import (
    valid_cnpj, valid_cpf, valid_iban, valid_isbn, valid_issn, valid_orcid)
from llmwiki.normalize.detectors.quantities import canonical_number, detect as detect_qty
from llmwiki.normalize.engine import findings
from llmwiki.normalize.masking import is_protected, protected_spans


# ---------------------------------------------------------------- checksums
def test_cpf_checksum():
    assert valid_cpf("529.982.247-25")
    assert valid_cpf("52998224725")
    assert not valid_cpf("529.982.247-26")       # DV errado
    assert not valid_cpf("111.111.111-11")       # todos iguais


def test_cnpj_numeric_and_alphanumeric():
    assert valid_cnpj("11.222.333/0001-81")
    assert not valid_cnpj("11.222.333/0001-82")
    assert valid_cnpj("12.ABC.345/01DE-35")      # vetor publicado (SERPRO)
    assert not valid_cnpj("12.ABC.345/01DE-36")


def test_isbn_10_and_13():
    assert valid_isbn("0-306-40615-2")
    assert valid_isbn("978-0-306-40615-7")
    assert not valid_isbn("978-0-306-40615-8")
    assert not valid_isbn("0-306-40615-3")


def test_issn_orcid_iban():
    assert valid_issn("0378-5955")
    assert not valid_issn("0378-5956")
    assert valid_orcid("0000-0002-1825-0097")
    assert not valid_orcid("0000-0002-1825-0098")
    assert valid_iban("GB82 WEST 1234 5698 7654 32")
    assert not valid_iban("GB82 WEST 1234 5698 7654 33")


def test_invalid_identifier_is_hallucination_signal():
    rep = analyze("Livro com ISBN 978-0-306-40615-8 citado.")
    hits = [(sev, rule) for sev, rule, _, _ in
            findings("p.md", rep, machine=True)]
    assert ("error", "policy.identifier_invalid") in hits
    # em página humana o mesmo sinal é warn
    hits = [(sev, rule) for sev, rule, _, _ in
            findings("p.md", rep, machine=False)]
    assert ("warn", "policy.identifier_invalid") in hits


# -------------------------------------------------------------------- datas
def _iso(text, locale="pt-BR"):
    return [(m.canonical, m.confidence) for m in detect_dates(text, locale)]


def test_dates_numeric_disambiguation():
    assert _iso("em 25/12/2024") == [("2024-12-25", "extracted")]   # dia>12
    assert _iso("em 12/03/2024") == [("2024-03-12", "inferred")]    # locale pt
    assert _iso("on 12/03/2024", "en-US") == [("2024-12-03", "inferred")]
    assert _iso("em 13/13/2024")[0][1] == "ambiguous"               # descartada


def test_dates_prose_pt_en_and_iso():
    assert ("2026-07-05", "extracted") in _iso("5 de julho de 2026")
    assert ("2024-03-12", "extracted") in _iso("March 12, 2024")
    assert ("2024-03-12", "extracted") in _iso("12 Mar 2024")
    assert ("2026-07-01", "extracted") in _iso("prazo 2026-07-01")
    assert ("2026-03", "inferred") in _iso("desde 2026-03")         # ano-mês


# --------------------------------------------------------------- quantidades
def test_canonical_number_locales():
    assert canonical_number("1.234,56") == (1234.56, "extracted")   # ambos
    assert canonical_number("1,234", "pt-BR") == (1.234, "inferred")
    assert canonical_number("1,234", "en-US") == (1234.0, "inferred")
    assert canonical_number("12,5", "pt-BR") == (12.5, "extracted")


def test_quantities_si_and_false_positive():
    ms = detect_qty("latência de 250 ms e 10 GiB de RAM")
    by_unit = {m.data["unit"]: m for m in ms}
    assert by_unit["ms"].data["si"] == {"value": 0.25, "unit": "s"}
    assert by_unit["GiB"].data["si"]["value"] == 10 * 2**30
    assert not detect_qty("temos 10 mais coisas")                   # 'm' não casa
    # unidade de 1 letra é inferred (risco de FP, §1.6)
    assert detect_qty("pesa 5 g")[0].confidence == "inferred"


# ------------------------------------------------------------------ máscara
def test_masking_fences_inline_and_unclosed():
    text = "usa postgres\n```\npostgres aqui\n```\ne `postgres` inline"
    spans = protected_spans(text)
    fence = text.index("```")
    assert is_protected(spans, fence + 4, fence + 12)               # dentro da fence
    inline = text.rindex("`postgres`")
    assert is_protected(spans, inline, inline + 5)
    assert not is_protected(spans, 4, 12)                           # prosa livre
    # fence não fechada protege até o fim
    spans2 = protected_spans("texto\n```\nsem fechamento postgres")
    assert is_protected(spans2, 10, 20)


def test_citations_section_is_verbatim():
    text = "corpo postgres\n\n# Citations\n\n[1] postgres manual\n"
    out = rewrite(text, analyze(text))
    assert "corpo PostgreSQL" in out                    # só o corpo muda
    assert "[1] postgres manual" in out                 # Citations verbatim


# ---------------------------------------------------------------- gazetteer
def test_gazetteer_punctuation_apostrophe_and_url_scheme():
    rep = analyze("usamos nodejs. livros da o’reilly. veja postgres://host")
    canon = {m.canonical for m in rep.matches if m.kind == "entity"}
    assert {"Node.js", "O'Reilly"} <= canon
    assert "PostgreSQL" not in canon                                # esquema de URL


def test_rewrite_idempotent_end_to_end():
    text = ("Migramos de postgres para PostgreSQL em k8s; artigo da NIPS.\n"
            "```\nkubectl -n k8s postgres\n```\n")
    r1 = rewrite(text, analyze(text))
    r2 = rewrite(r1, analyze(r1))
    assert r1 == r2
    assert "Kubernetes" in r1 and "NeurIPS" in r1
    assert "kubectl -n k8s postgres" in r1                          # fence intocada


def test_authority_records_extend_gazetteer():
    gaz = Gazetteer.load([{"canonical": "DuckDB", "aliases": ["duckdb", "duck db"],
                           "authority": "stack", "qid": "Q107647697"}])
    rep = analyze("testamos duck db ontem", gaz=gaz)
    assert any(m.canonical == "DuckDB" for m in rep.matches)


def test_semver_is_annex_only_never_rewritten():
    text = "lançamos a v1.2.3 ontem"
    rep = analyze(text)
    assert any(m.subkind == "semver" and m.confidence == "inferred"
               for m in rep.matches)
    assert rewrite(text, rep) == text
    assert not findings("p.md", rep, machine=True)                  # sem residual


# --------------------------------------------------------- normas e sensível
def test_standards_and_named_regulators():
    rep = analyze("conforme iso 27001:2022, RFC 793 e a lgpd")
    canon = {m.canonical for m in rep.matches if m.kind == "standard"}
    assert "ISO 27001:2022" in canon
    assert "RFC 793" in canon
    assert "Lei nº 13.709/2018 (LGPD)" in canon


def test_sensitive_flag_needs_valid_checksum():
    assert analyze("CPF do cliente: 529.982.247-25").sensitive
    assert not analyze("número 529.982.247-26 inválido").sensitive


def test_priority_identifier_beats_quantity():
    # CPF sem máscara não pode virar "quantidade"
    rep = analyze("cadastro 52998224725")
    kinds = {m.kind for m in rep.matches}
    assert "identifier" in kinds
