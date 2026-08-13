"""v1.4 (DATA-1) — doctor de invariantes + reject-newer + ledger."""
from __future__ import annotations
import pytest
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import SCHEMA_VERSIONS, SchemaTooNewError, connect
from corpusmith.settings import Settings
from corpusmith.usecases.diagnose import DiagnoseSystem


def _doc(rel, title, body="corpo.", **meta):
    return OKFDocument(rel_path=rel, body=f"# {title}\n\n{body}",
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only", **meta))


def test_clean_bundle_passes(settings, kb):
    BundleWriter(kb).write([_doc("concepts/a.md", "A")],
                           log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    result = DiagnoseSystem(settings).execute()
    assert result["ok"] and result["counts"]["error"] == 0


def test_doctor_detects_and_repairs_index_orphan(settings, kb):
    BundleWriter(kb).write([_doc("concepts/a.md", "A")],
                           log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    # injeta um chunk órfão (página que não existe no bundle)
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO chunks(page,ord,text) VALUES "
                "('concepts/fantasma.md', 0, 'lixo')")
    idx.commit(); idx.close()
    findings = DiagnoseSystem(settings).execute()["findings"]
    assert any(f["inv"] == "INV-001" for f in findings)


def test_repair_rebuilds_and_clears_orphan(settings, kb):
    BundleWriter(kb).write([_doc("concepts/a.md", "A")],
                           log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO chunks(page,ord,text) VALUES "
                "('concepts/fantasma.md', 0, 'lixo')")
    idx.commit(); idx.close()
    fixed = DiagnoseSystem(settings, repair=True).execute()
    assert fixed["ok"] and fixed["repaired"]["mode"] == "full"
    assert not any(f["inv"] == "INV-001" for f in fixed["findings"])


def test_repair_com_embeddings_populadas_nao_estoura_fk(settings, kb):
    """Regressão do incidente v1.9: com jobs `embed` concluindo, o repair
    do doctor (rebuild full) estourava IntegrityError na FK
    embeddings.chunk_id → chunks(id) — o caminho de recuperação era ele
    mesmo irrecuperável."""
    BundleWriter(kb).write([_doc("concepts/a.md", "A")],
                           log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    chunk = idx.execute("SELECT id FROM chunks").fetchone()["id"]
    idx.execute("INSERT INTO embeddings(chunk_id, model, vec) "
                "VALUES (?,?,?)", (chunk, "m", b"\x00"))
    # índice sobre outra revisão (INV-002) — o estado que pede repair
    idx.execute("UPDATE index_meta SET value='cafebabe' "
                "WHERE key='bundle_head'")
    idx.commit(); idx.close()
    fixed = DiagnoseSystem(settings, repair=True).execute()
    assert fixed["ok"] and fixed["repaired"]["mode"] == "full"


def test_doctor_flags_stale_generation(settings, kb):
    BundleWriter(kb).write([_doc("concepts/a.md", "A")],
                           log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    idx.execute("UPDATE index_meta SET value='g0:antiga' "
                "WHERE key='index_generation'")
    idx.commit(); idx.close()
    findings = DiagnoseSystem(settings).execute()["findings"]
    assert any(f["inv"] == "INV-002" for f in findings)


def test_doctor_flags_broken_pipeline_and_cognitive_orphan(settings, kb):
    BundleWriter(kb).write([_doc("concepts/a.md", "A")],
                           log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("INSERT INTO pipelines(name, spec) VALUES "
               "('quebrado', '{\"stages\":[{\"job\":\"nao-existe\"}]}')")
    rt.commit(); rt.close()
    cog = connect(settings.app_support / "cognitive.db")
    cog.execute("INSERT INTO accessibility(item, level) VALUES "
                "('concepts/sumiu.md', 'recall')")
    cog.commit(); cog.close()
    findings = DiagnoseSystem(settings, known_jobs={"embed"}).execute()
    invs = {f["inv"] for f in findings["findings"]}
    assert "PIPE" in invs and "COG" in invs
    assert findings["counts"]["warn"] >= 2


def test_connect_rejects_future_schema(settings):
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("UPDATE _meta SET value = ? WHERE key='schema_version'",
               (str(SCHEMA_VERSIONS["runtime.db"] + 5),))
    rt.commit(); rt.close()
    with pytest.raises(SchemaTooNewError):
        connect(settings.app_support / "runtime.db")


def test_migration_ledger_records_first_stamp(settings):
    rt = connect(settings.app_support / "runtime.db")
    rows = rt.execute("SELECT from_version, to_version FROM schema_migrations "
                      "ORDER BY id").fetchall()
    rt.close()
    assert rows and rows[0]["to_version"] == SCHEMA_VERSIONS["runtime.db"]
    assert rows[0]["from_version"] is None       # banco nasceu na versão atual


def test_review_semanal_nao_deixa_o_doctor_vermelho(settings, kb):
    """Achado da PRIMEIRA execução da CI numa segunda-feira (package
    smoke): `review_weekly` escreve `reviews/<semana>.md` e COMMITA sem
    reindexar — INV-002 error até o próximo rebuild. Mesma classe do bug
    do `leiden`, corrigido no F2 ("o job não deixa o doctor vermelho");
    o ramo semanal do Scheduler nunca tinha sido exercitado num smoke."""
    from corpusmith.jobs import REGISTRY
    BundleWriter(kb).write([_doc("concepts/a.md", "A")],
                           log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)            # consolidate/embed carimbam o índice
    assert DiagnoseSystem(settings).execute()["ok"], "cenário já sujo"
    REGISTRY["review_weekly"](settings, {}, lambda *a, **k: None)
    rel = DiagnoseSystem(settings).execute()
    erros = [f for f in rel["findings"] if f["severity"] == "error"]
    assert not erros, f"o job deixou o doctor vermelho: {erros}"
