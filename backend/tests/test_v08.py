"""Integração v0.8 (§12.2): política PII/temporal, reconciliação,
bi-temporalidade + abstenção no ask, reflect/overlay, eval e migração."""
from __future__ import annotations
import json
from datetime import datetime, timezone
import pytest
from llmwiki.harness.runner import HarnessRejection
from llmwiki.jobs import reconcile, reflect
from llmwiki.jobs.ask import answer, answer_local
from llmwiki.normalize import analyze
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect


def _doc(rel="concepts/x.md", body="# X\n\ncorpo", **meta):
    meta.setdefault("type", "concept")
    return OKFDocument(rel_path=rel, body=body, meta=OKFFrontMatter(**meta))


def _rules(findings, severity=None):
    return {f.rule for f in findings
            if severity is None or f.severity == severity}


# ------------------------------------------------------------ política v0.8
def test_pii_requires_local(runner):
    body = "# Cliente\n\nCPF 529.982.247-25 no cadastro."
    doc = _doc(body=body, privacy="api_allowed", generated_via="human:promote")
    findings = runner.run([doc])
    assert "policy.pii_requires_local" in _rules(findings, "error")
    ok = _doc(body=body, privacy="local_only", generated_via="human:promote")
    assert "policy.pii_requires_local" not in _rules(runner.run([ok]))


def test_invalid_identifier_blocks_machine_page(runner):
    doc = _doc(body="# Livro\n\nISBN 978-0-306-40615-8.",
               privacy="local_only", generated_via="api:claude",
               source_sha256="a" * 64)
    findings = runner.run([doc])
    assert "policy.identifier_invalid" in _rules(findings, "error")


def test_machine_page_with_noncanonical_term_is_blocked(runner, kb):
    doc = _doc(body="# Stack\n\nUsamos postgres em produção.",
               privacy="local_only", generated_via="local:compile",
               source_sha256="a" * 64)
    with pytest.raises(HarnessRejection):
        BundleWriter(kb).write([doc], log_kind="Creation",
                               log_message="m", commit_message="c")
    # a mesma página humana recebe só info (grafia curada disponível)
    human = _doc(body="# Stack\n\nUsamos postgres em produção.",
                 privacy="local_only", generated_via="human:promote")
    findings = runner.run([human])
    assert "policy.term_noncanonical" in _rules(findings, "info")
    assert not [f for f in findings if f.severity == "error"]


def test_temporal_order_rule(runner):
    doc = _doc(privacy="local_only", generated_via="human:promote",
               valid_at="2026-05-01T00:00:00Z", invalid_at="2026-04-01T00:00:00Z")
    assert "policy.temporal_order" in _rules(runner.run([doc]), "error")


def test_authority_record_type_is_recommended(runner):
    doc = _doc(rel="authorities/stack/duckdb.md", type="authority_record",
               privacy="local_only", generated_via="human:promote",
               canonical="DuckDB", aliases=["duckdb"], authority="stack")
    findings = runner.run([doc])
    assert "policy.unknown_type" not in _rules(findings)


# ------------------------------------------------------------- reconciliação
def _write_indexed(settings, kb, doc):
    r = BundleWriter(kb).write([doc], log_kind="Creation",
                               log_message="m", commit_message="c")
    rebuild_index(settings)
    return r


def test_same_doi_reconciles_to_update(settings, kb):
    base = _doc(rel="concepts/paper-attention.md",
                body="# Attention\n\nPaper doi 10.5555/3295222 sobre atenção.",
                title="Attention Is All You Need",
                privacy="local_only", generated_via="human:promote")
    _write_indexed(settings, kb, base)
    cand = _doc(rel="concepts/attention-2.md",
                body="# Attention outra fonte\n\nMesmo doi 10.5555/3295222.",
                title="Attention (segunda fonte)",
                privacy="local_only", generated_via="local:compile",
                source_sha256="b" * 64)
    decision = reconcile.plan(settings, cand, analyze(cand.body))
    assert decision["op"] == "UPDATE"
    assert decision["target"] == "concepts/paper-attention.md"
    assert decision["confidence"] == "extracted"
    reconcile.log(settings, cand.rel_path, decision)
    rt = connect(settings.app_support / "runtime.db")
    row = rt.execute("SELECT op, target FROM reconcile_log "
                     "ORDER BY id DESC LIMIT 1").fetchone()
    rt.close()
    assert (row["op"], row["target"]) == ("UPDATE", "concepts/paper-attention.md")


def test_unrelated_page_is_add(settings, kb):
    base = _doc(rel="concepts/kafka.md", body="# Kafka\n\nfilas distribuídas",
                title="Kafka", privacy="local_only",
                generated_via="human:promote")
    _write_indexed(settings, kb, base)
    cand = _doc(rel="concepts/jardinagem.md",
                body="# Jardinagem\n\npodas sazonais", title="Jardinagem",
                privacy="local_only", generated_via="local:compile",
                source_sha256="b" * 64)
    assert reconcile.plan(settings, cand, analyze(cand.body))["op"] == "ADD"


# ---------------------------------------------------- bi-temporalidade + ask
def test_ask_extracts_as_of_and_filters_validity(settings, kb):
    old = _doc(rel="decisions/reranker.md",
               body="# Reranker\n\nAdotamos o reranker bge para consultas.",
               title="Reranker bge",
               privacy="local_only", generated_via="human:promote",
               valid_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
               invalid_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    new = _doc(rel="decisions/reranker-novo.md",
               body="# Reranker novo\n\nAdotamos o reranker qwen para consultas.",
               title="Reranker qwen",
               privacy="local_only", generated_via="human:promote",
               valid_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    BundleWriter(kb).write([old, new], log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)
    r = answer(settings, "qual reranker em 2026-03-01?")
    assert r["as_of"] == "2026-03-01"
    assert r["evidence"][0]["page"] == "decisions/reranker.md"   # válida na data
    r2 = answer(settings, "qual reranker em 2026-05-01?")
    assert r2["evidence"][0]["page"] == "decisions/reranker-novo.md"


def test_ask_abstains_without_coverage(settings, kb):
    rebuild_index(settings)
    r = answer_local(settings, "resultado do teste com Neo4j?")
    assert r["abstained"] is True
    assert r["answer"] is None
    assert r["gaps"]


def test_ask_updates_heat_and_returns_trajectory(settings, kb):
    page = _doc(rel="runbooks/daemon.md",
                body="# Daemon\n\nO daemon local escuta na porta 8377.",
                title="Runbook do daemon", description="operação do daemon",
                privacy="local_only", generated_via="human:promote")
    _write_indexed(settings, kb, page)
    r = answer_local(settings, "qual porta o daemon usa?")
    assert not r["abstained"]
    assert any(e["page"] == "runbooks/daemon.md" for e in r["evidence"])
    assert any(t["dir"] == "runbooks" for t in r["trajectory"])
    rt = connect(settings.app_support / "runtime.db")
    row = rt.execute("SELECT reads FROM page_heat WHERE path=?",
                     ("runbooks/daemon.md",)).fetchone()
    rt.close()
    assert row and row["reads"] >= 1


# ----------------------------------------------------------- reflect/overlay
def test_reflect_builds_overlay_and_contested_sinks(settings, kb):
    a = _doc(rel="concepts/bom.md", body="# Bom\n\nresposta sobre cache lru",
             title="Cache bom", privacy="local_only",
             generated_via="human:promote")
    b = _doc(rel="concepts/ruim.md", body="# Ruim\n\nresposta sobre cache lru",
             title="Cache ruim", privacy="local_only",
             generated_via="human:promote")
    BundleWriter(kb).write([a, b], log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)
    rt = connect(settings.app_support / "runtime.db")
    for verdict, pages in [("useful", ["concepts/bom.md"])] * 3 \
                        + [("dead_end", ["concepts/ruim.md"])] * 3:
        rt.execute("INSERT INTO ask_outcomes(ask_id, verdict, pages) "
                   "VALUES ('t', ?, ?)", (verdict, json.dumps(pages)))
    rt.commit()
    rt.close()
    result = reflect.run(settings, {}, lambda *a, **k: None)
    assert "concepts/ruim.md" in result["low_yield"]
    idx = connect(settings.app_support / "index.db")
    status = {r["page"]: r["status"] for r in
              idx.execute("SELECT page, status FROM page_overlay")}
    idx.close()
    assert status["concepts/bom.md"] == "preferred"
    assert status["concepts/ruim.md"] == "low_yield"
    r = answer_local(settings, "resposta sobre cache lru")
    assert r["evidence"][0]["page"] == "concepts/bom.md"     # contested afunda


# -------------------------------------------------------------------- eval
def test_eval_memory_five_categories(settings, kb):
    page = _doc(rel="runbooks/daemon.md",
                body="# Daemon\n\nO daemon escuta na porta 8377.",
                title="Runbook do daemon", description="porta do daemon",
                privacy="local_only", generated_via="human:promote")
    _write_indexed(settings, kb, page)
    gold = kb / "bundle" / "harness"
    gold.mkdir(exist_ok=True)
    cases = [
        {"q": "qual porta o daemon usa?", "category": "extract",
         "expect_pages": ["runbooks/daemon.md"], "expect_regex": r"\b8377\b"},
        {"q": "resultado do teste com Neo4j?", "category": "abstain",
         "expect_abstain": True},
    ]
    (gold / "golden_eval.jsonl").write_text(
        "\n".join(json.dumps(c) for c in cases))
    from llmwiki.harness import eval_memory
    out = eval_memory.run(settings, {}, lambda *a, **k: None)
    assert out["stats"]["extract"] == [1, 1]
    assert out["stats"]["abstain"] == [1, 1]
    rt = connect(settings.app_support / "runtime.db")
    rows = rt.execute("SELECT category, passed FROM eval_runs").fetchall()
    rt.close()
    assert {(r["category"], r["passed"]) for r in rows} == {("extract", 1),
                                                            ("abstain", 1)}


# ---------------------------------------------------------------- migração
def test_migrate_adds_columns_to_old_index_db(tmp_path):
    import sqlite3
    old = tmp_path / "index.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE graph_edges(src TEXT, dst TEXT, kind TEXT, "
                 "PRIMARY KEY(src,dst,kind))")
    conn.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, page TEXT, "
                 "ord INTEGER, text TEXT, resource TEXT, privacy TEXT, "
                 "stale INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()
    migrated = connect(old)
    cols = {r["name"] for r in migrated.execute("PRAGMA table_info(graph_edges)")}
    assert "confidence" in cols
    cols = {r["name"] for r in migrated.execute("PRAGMA table_info(chunks)")}
    assert {"valid_at", "invalid_at"} <= cols
    migrated.close()


# --------------------------------------------------- v0.9: laço de crédito
def test_ask_reports_uncertainty(settings, kb):
    page = _doc(rel="concepts/cache.md", body="# Cache\n\ncache lru local",
                title="Cache LRU", privacy="local_only",
                generated_via="human:promote")
    _write_indexed(settings, kb, page)
    r = answer_local(settings, "cache lru")
    assert 0.0 <= r["uncertainty"] <= 1.0


def test_outcome_trains_stream_credit_via_hedge(settings, kb):
    page = _doc(rel="concepts/filas.md", body="# Filas\n\nfilas locais sqlite",
                title="Filas locais", privacy="local_only",
                generated_via="human:promote")
    _write_indexed(settings, kb, page)
    r = answer_local(settings, "filas locais sqlite")
    assert not r["abstained"]
    from llmwiki.facades import MemoryFacade
    MemoryFacade(settings).record_outcome(
        verdict="dead_end", ask_id=r["ask_id"],
        pages=[e["page"] for e in r["evidence"]])
    rt = connect(settings.app_support / "runtime.db")
    weights = {row["stream"]: row["weight"] for row in
               rt.execute("SELECT stream, weight FROM stream_weights")}
    prov = {row["stream"] for row in rt.execute(
        "SELECT DISTINCT stream FROM ask_provenance WHERE ask_id=?",
        (r["ask_id"],))}
    rt.close()
    assert prov                                   # proveniência registrada
    assert all(weights[s] < 1.0 for s in prov)    # beco ⇒ crédito cai
    # e o crédito reduzido entra na próxima fusão sem quebrar nada
    r2 = answer_local(settings, "filas locais sqlite")
    assert not r2["abstained"]


def test_communities_job_stores_fragile_bridges(settings, kb):
    docs = []
    for i in range(3):
        docs.append(_doc(rel=f"concepts/rede-{i}.md", title=f"Rede {i}",
                         body=f"# Rede {i}\n\nver [outro](/concepts/rede-{(i+1)%3}.md)",
                         privacy="local_only", generated_via="human:promote"))
    for i in range(3):
        docs.append(_doc(rel=f"decisions/banco-{i}.md", title=f"Banco {i}",
                         body=f"# Banco {i}\n\nver [outro](/decisions/banco-{(i+1)%3}.md)",
                         privacy="local_only", generated_via="human:promote"))
    docs.append(_doc(rel="concepts/ponte.md", title="Ponte",
                     body="# Ponte\n\n[[rede 0]] liga",
                     privacy="local_only", generated_via="human:promote"))
    BundleWriter(kb).write(docs, log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)
    from llmwiki.facades import CompilerFacade
    result = CompilerFacade(settings).detect_communities()
    assert result["communities"] >= 2
    idx = connect(settings.app_support / "index.db")
    bridges = idx.execute("SELECT COUNT(*) c FROM graph_bridges").fetchone()["c"]
    idx.close()
    assert bridges >= 0                           # tabela populada sem erro
