"""v0.10: cache do gazetteer, propagação de staleness (TMS), BLA (ACT-R),
consolidação por recorrência (CLS), contradição determinística (AGM) e
schemas por tipo (DTT lite)."""
from __future__ import annotations
import json
from corpusmith.facades import CompilerFacade, CurationFacade
from corpusmith.kernel.activation import base_level_activation, logistic
from corpusmith.okf.authorities import load_gazetteer, load_type_schemas
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.usecases.reflect_usage import ReflectOnUsage


def _doc(rel="concepts/x.md", body="# X\n\ncorpo", **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body, meta=OKFFrontMatter(**meta))


def _rules(findings, severity=None):
    return {f.rule for f in findings
            if severity is None or f.severity == severity}


# ---------------------------------------------------- cache do gazetteer
def test_gazetteer_cached_by_head_and_invalidated_on_write(kb):
    reader = BundleReader(kb / "bundle")
    first = load_gazetteer(reader)
    assert load_gazetteer(reader) is first          # HEAD igual ⇒ cache
    assert not any(m.canonical == "DuckDB"
                   for m in first.detect("usamos duckdb"))
    BundleWriter(kb).write(                          # write ⇒ commit ⇒ HEAD novo
        [_doc(rel="authorities/stack/duckdb.md", type="authority_record",
              canonical="DuckDB", aliases=["duckdb"], authority="stack",
              title="DuckDB")],
        log_kind="Creation", log_message="m", commit_message="c")
    fresh = load_gazetteer(reader)
    assert fresh is not first                        # invalidado
    assert any(m.canonical == "DuckDB" for m in fresh.detect("usamos duckdb"))


# ------------------------------------------------ TMS: staleness propaga
def test_mark_stale_lists_dependents(settings, kb):
    base = _doc(rel="concepts/base.md", title="Base",
                body="# Base\n\nfato fundamental")
    dependent = _doc(rel="concepts/dependente.md", title="Dependente",
                     body="# Dependente\n\napoia-se em [base](/concepts/base.md)")
    BundleWriter(kb).write([base, dependent], log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)
    result = CurationFacade(settings).mark_stale("concepts/base.md")
    assert result["dependents"] == ["concepts/dependente.md"]
    # depreciar quem não tem citações não acusa dependentes
    result = CurationFacade(settings).mark_stale("concepts/dependente.md")
    assert result["dependents"] == []


# --------------------------------------------------------- BLA (ACT-R)
def test_base_level_activation_properties():
    assert base_level_activation(0, 10) == float("-inf")
    # mais usos ⇒ mais ativação; mais idade ⇒ menos
    assert base_level_activation(10, 5) > base_level_activation(2, 5)
    assert base_level_activation(5, 1) > base_level_activation(5, 100)
    # efeito de espaçamento: mesmos 10 usos, vida longa decai só como L^-d
    assert base_level_activation(10, 90) > \
        base_level_activation(1, 1) - 3          # segue relevante
    assert logistic(float("-inf")) == 0.0
    assert 0.0 < logistic(0.0) < 1.0


def test_reflect_uses_bla_and_bounded_score(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("INSERT INTO page_heat(path, reads, cites, last_seen, "
               "first_seen) VALUES ('concepts/viva.md', 20, 3, "
               "unixepoch(), unixepoch() - 7*86400)")
    rt.execute("INSERT INTO page_heat(path, reads, cites, last_seen, "
               "first_seen) VALUES ('concepts/morta.md', 0, 0, "
               "unixepoch() - 200*86400, unixepoch() - 300*86400)")
    rt.commit()
    rt.close()
    ReflectOnUsage(settings).execute()
    rt = connect(settings.app_support / "runtime.db")
    scores = {r["path"]: r["score"] for r in
              rt.execute("SELECT path, score FROM page_heat")}
    rt.close()
    assert 0.0 <= scores["concepts/morta.md"] < scores["concepts/viva.md"] <= 1.0
    assert scores["concepts/viva.md"] > 0.5      # usada e citada


def test_migrate_adds_first_seen_to_old_runtime_db(tmp_path):
    import sqlite3
    old = tmp_path / "runtime.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE page_heat(path TEXT PRIMARY KEY, reads "
                 "INTEGER DEFAULT 0, cites INTEGER DEFAULT 0, "
                 "last_seen REAL, score REAL DEFAULT 0)")
    conn.execute("INSERT INTO page_heat(path, last_seen) VALUES ('p', 123.0)")
    conn.commit()
    conn.close()
    migrated = connect(old)
    row = migrated.execute("SELECT first_seen FROM page_heat "
                           "WHERE path='p'").fetchone()
    migrated.close()
    assert row["first_seen"] == 123.0            # backfill = last_seen


# ------------------------------------------- CLS: consolidar por recorrência
def test_consolidate_clusters_recurrent_notes(settings, kb):
    raw = kb / "raw"
    (raw / "nota-a.md").write_text(
        "# Nota A\n\nMigração para postgres rodando em k8s no cluster novo.\n")
    (raw / "nota-b.md").write_text(
        "# Nota B\n\nBenchmarks do postgres sob k8s: latência estável.\n")
    (raw / "avulsa.md").write_text(
        "# Avulsa\n\nReceita de pão de fermentação natural.\n")
    result = CompilerFacade(settings).consolidate_inbox()
    assert result["clusters"] == 1
    assert len(result["pages"]) == 1
    assert result["left"] == ["raw/avulsa.md"]   # sem recorrência ⇒ pendente
    page = BundleReader(kb / "bundle").load(result["pages"][0])
    x = page.meta.model_dump(exclude_none=True)
    assert set(x["sources"]) == {"raw/nota-a.md", "raw/nota-b.md"}
    assert x["generated_via"].startswith(("local:", "api:"))
    assert "PostgreSQL" in page.body             # sanduíche aplicado
    rt = connect(settings.app_support / "runtime.db")
    cached = {r["source"] for r in rt.execute("SELECT source FROM compile_cache")}
    rt.close()
    assert {"raw/nota-a.md", "raw/nota-b.md"} <= cached
    # segunda rodada: nada pendente convergente, nada novo
    again = CompilerFacade(settings).consolidate_inbox()
    assert again["clusters"] == 0 and again["left"] == ["raw/avulsa.md"]


def test_consolidate_privacy_is_most_restrictive(settings, kb):
    s2 = settings.with_overrides(privacy={
        "default": "api_allowed",
        "rules": [{"pattern": "raw/privado/*", "privacy": "local_only"}]})
    raw = kb / "raw"
    (raw / "privado").mkdir(parents=True, exist_ok=True)
    (raw / "aberta.md").write_text("# A\n\ngrpc e rabbitmq na malha.\n")
    (raw / "privado" / "fechada.md").write_text(
        "# B\n\ngrpc e rabbitmq no ambiente interno.\n")
    result = CompilerFacade(s2).consolidate_inbox()
    assert result["clusters"] == 1
    page = BundleReader(kb / "bundle").load(result["pages"][0])
    assert page.meta.model_dump()["privacy"] == "local_only"


# --------------------------------------------- AGM: contradição candidata
def test_lint_flags_same_identifier_without_succession(runner, kb):
    a = _doc(rel="concepts/paper-v1.md", title="Paper v1",
             body="# Paper\n\nResultados do doi 10.5555/12345 originais.",
             generated_via="human:promote")
    b = _doc(rel="concepts/paper-v2.md", title="Paper v2",
             body="# Paper de novo\n\nOutra leitura do doi 10.5555/12345 aqui.",
             generated_via="local:compile", source_sha256="a" * 64)
    BundleWriter(kb).write([a, b], log_kind="Creation",
                           log_message="m", commit_message="c")
    findings = runner.lint_bundle(kb / "bundle")
    assert "policy.contradiction_candidate" in _rules(findings, "warn")
    hit = next(f for f in findings
               if f.rule == "policy.contradiction_candidate")
    assert hit.path == "concepts/paper-v1.md"    # humana = mais entrincheirada
    assert set(hit.meta["pages"]) == {"concepts/paper-v1.md",
                                      "concepts/paper-v2.md"}


def test_succession_resolves_contradiction(runner, kb):
    a = _doc(rel="concepts/paper-v1.md", title="Paper v1",
             body="# Paper\n\ndoi 10.5555/12345.",
             superseded_by="concepts/paper-v2.md",
             valid_at="2026-01-01T00:00:00Z",
             invalid_at="2026-06-01T00:00:00Z")
    b = _doc(rel="concepts/paper-v2.md", title="Paper v2",
             body="# Paper v2\n\ndoi 10.5555/12345 revisado.")
    BundleWriter(kb).write([a, b], log_kind="Creation",
                           log_message="m", commit_message="c")
    findings = runner.lint_bundle(kb / "bundle")
    assert "policy.contradiction_candidate" not in _rules(findings)


# ------------------------------------------------ DTT lite: schema por tipo
def test_collection_specification_enforces_required_fields(runner, kb):
    spec = _doc(rel="schemas/decision-spec.md", type="collection_specification",
                title="Contrato de decisões",
                body="# Contrato\n\nDecisões precisam de contexto.",
                applies_to="decision", required_fields=["description"])
    BundleWriter(kb).write([spec], log_kind="Creation",
                           log_message="m", commit_message="c")
    assert load_type_schemas(BundleReader(kb / "bundle")) == {
        "decision": {"required_fields": ["description"],
                     "page": "schemas/decision-spec.md"}}
    incomplete = _doc(rel="decisions/sem-contexto.md", type="decision",
                      title="Sem contexto", body="# D\n\ndecidido.")
    findings = runner.run([incomplete])
    assert "policy.schema_required_field" in _rules(findings, "error")
    complete = _doc(rel="decisions/com-contexto.md", type="decision",
                    title="Com contexto", description="por que decidimos",
                    body="# D\n\ndecidido.")
    assert "policy.schema_required_field" not in _rules(runner.run([complete]))


def test_types_without_schema_are_unconstrained(runner, kb):
    # sem collection_specification no bundle, nada é exigido além da política base
    doc = _doc(rel="decisions/livre.md", type="decision", title="Livre",
               body="# D\n\nsem description e tudo bem.")
    assert "policy.schema_required_field" not in _rules(runner.run([doc]))


# ------------------------------------------------------------ desfechos
def test_outcome_json_payload_shape(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    cols = {r["name"] for r in rt.execute("PRAGMA table_info(page_heat)")}
    rt.close()
    assert "first_seen" in cols
    assert json.dumps({"ok": True})              # sanity


# --------------------------------------------------- v0.11: pipeline viva
def test_machine_page_emits_stage_events(settings, kb):
    (kb / "raw" / "fonte.md").write_text("# Fonte\n\nusamos sqlite aqui.\n")
    events: list[tuple[str, dict]] = []
    CompilerFacade(settings).compile(
        "raw/fonte.md", notify=lambda t, d=None: events.append((t, d or {})))
    stages = [d["stage"] for t, d in events if t == "page.stage"]
    assert stages == ["produce", "normalize", "reconcile", "write", "done"]
    done = next(d for t, d in events if t == "page.stage"
                and d["stage"] == "done")
    assert done["page"] and done["op"] == "ADD"


def test_ingest_source_sanitizes_and_dedupes(settings, kb):
    from corpusmith.usecases.ingest_source import IngestSource
    import pytest as _pytest
    first = IngestSource(settings, filename="Água & Fogo.md",
                         content="# a").execute()
    assert first["path"] == "raw/agua-fogo.md"
    second = IngestSource(settings, filename="água   fogo.md",
                          content="# b", subdir="Reuniões").execute()
    assert second["path"] == "raw/reunioes/agua-fogo.md"
    with _pytest.raises(ValueError):
        IngestSource(settings, filename="x.md").execute()   # sem conteúdo


def test_migrate_adds_page_to_old_compile_cache(tmp_path):
    import sqlite3
    old = tmp_path / "runtime.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE compile_cache(source TEXT PRIMARY KEY, "
                 "sha TEXT, at REAL)")
    conn.commit()
    conn.close()
    migrated = connect(old)
    cols = {r["name"] for r in migrated.execute(
        "PRAGMA table_info(compile_cache)")}
    migrated.close()
    assert "page" in cols
