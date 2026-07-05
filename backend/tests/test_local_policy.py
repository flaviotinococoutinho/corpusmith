"""Política local (§4.3): privacy obrigatório, proveniência por máquina,
citações só para api:*, promoção humana liberada (§9 aceite)."""
from __future__ import annotations
from datetime import datetime, timezone
from llmwiki.okf.document import OKFDocument, OKFFrontMatter


def _doc(rel="concepts/x.md", body="# X\n\ncorpo", **meta):
    meta.setdefault("type", "concept")
    return OKFDocument(rel_path=rel, body=body, meta=OKFFrontMatter(**meta))


def _rules(findings, severity=None):
    return {f.rule for f in findings
            if severity is None or f.severity == severity}


def test_privacy_is_required_for_every_written_page(runner):
    findings = runner.run([_doc()])
    assert "policy.privacy_required" in _rules(findings, "error")


def test_machine_generated_requires_source_sha256(runner):
    findings = runner.run([_doc(privacy="local_only",
                                generated_via="local:compile")])
    assert "policy.source_sha_required" in _rules(findings, "error")
    findings = runner.run([_doc(privacy="local_only",
                                generated_via="api:claude",
                                source_sha256="a" * 64,
                                body_ok=True)])
    assert "policy.source_sha_required" not in _rules(findings)


def test_human_promotion_passes_without_source_sha256(runner):
    """§9: promoção humana passa no Harness sem source_sha256."""
    doc = _doc(privacy="local_only", generated_via="human:promote",
               confidence="human_approved", source="chat")
    findings = runner.run([doc])
    assert not [f for f in findings if f.severity == "error"], findings


def test_api_content_without_citations_is_blocked(runner):
    """§9: página de API sem # Citations → bloqueada (política)."""
    doc = _doc(privacy="api_allowed", generated_via="api:claude",
               source_sha256="a" * 64)
    findings = runner.run([doc])
    assert "policy.citation_required" in _rules(findings, "error")
    hit = next(f for f in findings if f.rule == "policy.citation_required")
    assert not hit.okf_conformance   # política local, NÃO conformidade


def test_api_content_with_valid_citations_passes(runner):
    body = ("# X\n\nafirmação [1]\n\n# Citations\n\n[1] concepts/base.md\n")
    doc = _doc(body=body, privacy="api_allowed", generated_via="api:claude",
               source_sha256="a" * 64)
    findings = runner.run([doc])
    assert not [f for f in findings if "citation" in f.rule]


def test_api_citation_refs_must_be_listed(runner):
    body = ("# X\n\num [1] e dois [2]\n\n# Citations\n\n[1] concepts/a.md\n")
    doc = _doc(body=body, privacy="api_allowed", generated_via="api:claude",
               source_sha256="a" * 64)
    findings = runner.run([doc])
    assert "policy.citation_invalid" in _rules(findings, "error")


def test_local_generated_needs_no_citations(runner):
    doc = _doc(privacy="local_only", generated_via="local:compile",
               source_sha256="a" * 64)
    findings = runner.run([doc])
    assert not [f for f in findings if "citation" in f.rule]


def test_bad_commit_ref_is_error(runner):
    doc = _doc(privacy="local_only", generated_via="human:promote",
               body="# X\n\nvisto no commit deadbeef1234\n")
    findings = runner.run([doc])
    assert "policy.bad_commit_ref" in _rules(findings, "error")


def test_stale_as_of_with_real_commit_passes(runner, kb):
    head = runner.git.head()
    doc = _doc(privacy="local_only", generated_via="human:promote",
               stale_as_of=head[:12])
    findings = runner.run([doc])
    assert "policy.bad_commit_ref" not in _rules(findings)


def test_unknown_type_is_info_only(runner):
    doc = _doc(type="tipo_inventado", privacy="local_only",
               generated_via="human:promote")
    findings = runner.run([doc])
    assert "policy.unknown_type" in _rules(findings, "info")
    assert not [f for f in findings if f.severity == "error"]


def test_schema_shrink_without_supersedes(runner, bundle):
    from conftest import write_page
    old = ("---\ntype: schema_specification\nprivacy: local_only\n"
           "generated_via: human:promote\n---\n\n# S\n\n## Schema\n\n"
           "| campo | tipo |\n|---|---|\n| id | int |\n| nome | str |\n")
    write_page(bundle, "schemas/s.md", old)
    new = _doc(rel="schemas/s.md", type="schema_specification",
               privacy="local_only", generated_via="human:promote",
               body="# S\n\n## Schema\n\n| campo | tipo |\n|---|---|\n"
                    "| id | int |\n")
    findings = runner.run([new])
    assert "policy.schema_shrink" in _rules(findings, "error")


def test_release_mode_hardens_broken_links(runner):
    doc = _doc(privacy="local_only", generated_via="human:promote",
               body="# X\n\n[quebrado](/concepts/nada.md)\n")
    assert "policy.release_broken_link" not in _rules(runner.run([doc]))
    findings = runner.run([doc], mode="release")
    assert "policy.release_broken_link" in _rules(findings, "error")
