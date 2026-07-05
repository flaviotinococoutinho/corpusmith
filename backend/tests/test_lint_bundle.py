"""Golden bundles (v0.6 §7 + casos novos v0.7 §9): lint varre arquivos CRUS."""
from __future__ import annotations
from conftest import write_page


GOOD = """---
type: concept
title: Página válida
privacy: local_only
generated_via: human:promote
---

# Página válida

corpo
"""


def _rules(findings, severity=None):
    return {f.rule for f in findings
            if severity is None or f.severity == severity}


def test_fresh_bootstrap_has_zero_errors(runner, bundle):
    findings = runner.lint_bundle(bundle)
    assert not [f for f in findings if f.severity == "error"], findings


def test_file_without_frontmatter_is_conformance_error(runner, bundle):
    write_page(bundle, "concepts/solto.md", "# Solto\n\nsem yaml\n")
    findings = runner.lint_bundle(bundle)
    assert "okf.frontmatter_missing" in _rules(findings, "error")
    hit = next(f for f in findings if f.rule == "okf.frontmatter_missing")
    assert hit.okf_conformance and hit.path == "concepts/solto.md"


def test_invalid_yaml_is_conformance_error(runner, bundle):
    write_page(bundle, "concepts/ruim.md",
               "---\ntype: [não fechado\n---\n\ncorpo\n")
    findings = runner.lint_bundle(bundle)
    assert "okf.frontmatter_invalid" in _rules(findings, "error")


def test_missing_type_is_conformance_error(runner, bundle):
    write_page(bundle, "concepts/sem-type.md",
               "---\ntitle: Sem type\n---\n\ncorpo\n")
    findings = runner.lint_bundle(bundle)
    assert "okf.frontmatter_invalid" in _rules(findings, "error")


def test_malformed_page_does_not_hide_others(runner, bundle):
    write_page(bundle, "concepts/ok.md", GOOD)
    write_page(bundle, "concepts/solto.md", "# solto\n")
    findings = runner.lint_bundle(bundle)
    assert "okf.frontmatter_missing" in _rules(findings)
    # a página boa foi parseada e passou pelas outras camadas sem erro
    assert not [f for f in findings
                if f.path == "concepts/ok.md" and f.severity == "error"]


def test_broken_internal_link_is_warn_not_error(runner, bundle):
    write_page(bundle, "concepts/a.md", GOOD.replace(
        "corpo", "ver [b](/concepts/nao-existe.md)"))
    findings = runner.lint_bundle(bundle)
    assert "okf.broken_link" in _rules(findings, "warn")
    assert "okf.broken_link" not in _rules(findings, "error")


def test_absence_of_citations_emits_nothing_in_conformance(runner, bundle):
    write_page(bundle, "concepts/a.md", GOOD)   # human:*, sem # Citations
    findings = runner.lint_bundle(bundle)
    assert not [f for f in findings if "citation" in f.rule]


def test_reserved_checked_when_present_absence_ok(runner, bundle):
    # ausência de log.md nunca invalida
    (bundle / "log.md").unlink()
    findings = runner.lint_bundle(bundle)
    assert not [f for f in findings if f.severity == "error"]
    # heading não-ISO no log → warn
    (bundle / "log.md").write_text("# Log\n\n## ontem à noite\n\n* x\n")
    findings = runner.lint_bundle(bundle)
    assert "okf.log_heading" in _rules(findings, "warn")


def test_subdir_index_with_frontmatter_is_warn(runner, bundle):
    write_page(bundle, "concepts/index.md",
               "---\ntitle: proibido\n---\n\n# concepts\n")
    findings = runner.lint_bundle(bundle)
    assert "okf.reserved_frontmatter" in _rules(findings, "warn")


def test_root_index_okf_version_only_is_fine(runner, bundle):
    findings = runner.lint_bundle(bundle)   # bootstrap já cria com okf_version
    assert "okf.reserved_frontmatter" not in _rules(findings)
