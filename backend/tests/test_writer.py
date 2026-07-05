"""BundleWriter: gate do Harness + index/log/commit (v0.6 §2.6)."""
from __future__ import annotations
from datetime import datetime, timezone
import pytest
from llmwiki.harness.runner import HarnessRejection
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter


def _promoted(title="Padrão saga"):
    return OKFDocument(
        rel_path="decisions/padrao-saga.md",
        body=f"# {title}\n\nconteúdo promovido\n",
        meta=OKFFrontMatter(
            type="decision", title=title,
            timestamp=datetime.now(timezone.utc),
            **{"privacy": "local_only", "generated_via": "human:promote",
               "confidence": "human_approved", "source": "chat"}))


def test_write_creates_page_log_and_commit(kb):
    w = BundleWriter(kb)
    result = w.write([_promoted()], log_kind="Creation",
                     log_message="promovido de chat: Padrão saga",
                     commit_message="promote(decision): padrao-saga")
    assert result["pages"] == ["decisions/padrao-saga.md"]
    assert result["commit"] and w.git.has_commit(result["commit"])
    text = (kb / "bundle/decisions/padrao-saga.md").read_text()
    assert text.startswith("---\n")
    assert "generated_via: human:promote" in text
    log = (kb / "bundle/log.md").read_text()
    assert "[Creation] promovido de chat: Padrão saga" in log
    # index.md do diretório novo + raiz atualizada, sem frontmatter no subdir
    sub_index = (kb / "bundle/decisions/index.md").read_text()
    assert not sub_index.startswith("---")
    assert "padrao-saga.md" in sub_index
    root_index = (kb / "bundle/index.md").read_text()
    assert root_index.startswith("---\nokf_version:")
    assert "decisions/index.md" in root_index


def test_write_rejects_on_policy_error(kb):
    doc = _promoted()
    bad_meta = doc.meta.model_dump(exclude_none=True)
    bad_meta.pop("privacy")
    bad = OKFDocument(rel_path=doc.rel_path, body=doc.body,
                      meta=OKFFrontMatter(**bad_meta))
    with pytest.raises(HarnessRejection) as exc:
        BundleWriter(kb).write([bad], log_kind="Creation",
                               log_message="x", commit_message="x")
    assert any(f.rule == "policy.privacy_required"
               for f in exc.value.findings)
    assert not (kb / "bundle/decisions/padrao-saga.md").exists()


def test_written_bundle_lints_clean(kb, runner):
    BundleWriter(kb).write([_promoted()], log_kind="Creation",
                           log_message="m", commit_message="c")
    findings = runner.lint_bundle(kb / "bundle")
    assert not [f for f in findings if f.severity == "error"], findings


def test_timestamp_is_iso_on_disk_datetime_on_parse(kb):
    w = BundleWriter(kb)
    w.write([_promoted()], log_kind="Creation",
            log_message="m", commit_message="c")
    d = w.reader.load("decisions/padrao-saga.md")
    assert isinstance(d.meta.timestamp, datetime)
    raw = (kb / "bundle/decisions/padrao-saga.md").read_text()
    assert "timestamp: '20" in raw or "timestamp: 20" in raw   # ISO serializado
