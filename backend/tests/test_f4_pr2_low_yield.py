"""F4-PR2 (ADR-52, P-5) — o produto para de chamar beco de disputa.

`page_overlay.status = 'contested'` deriva de DESFECHO DE USO (dead_end
repetido) e cinco superfícies o exibiam como conflito factual. O valor,
as chaves e os rótulos viram `low_yield`; o conflito REAL chega na
F4-PR3 (`policy.factual_conflict`)."""
from __future__ import annotations
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _write(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def test_overlay_aceita_low_yield_e_recusa_contested(settings):
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO page_overlay(page, status) "
                "VALUES ('concepts/a.md', 'low_yield')")
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        idx.execute("INSERT INTO page_overlay(page, status) "
                    "VALUES ('concepts/b.md', 'contested')")
    idx.close()


def test_migracao_converte_contested_legado(settings, tmp_path):
    """Banco antigo com 'contested' abre no produto novo com o valor
    migrado — sem isso, todo index.db existente quebraria no CHECK."""
    import sqlite3
    from llmwiki.runtime.db import SCHEMA_VERSIONS, reset_initialized
    db = settings.app_support / "index.db"
    connect(db).close()                    # inicializa o banco do produto
    # simula o banco da versão anterior: sem CHECK novo, valor antigo
    raw = sqlite3.connect(db)
    raw.executescript(
        "DROP TABLE IF EXISTS page_overlay;"
        "CREATE TABLE page_overlay("
        "  page TEXT PRIMARY KEY,"
        "  status TEXT CHECK(status IN ('preferred','tentative','contested')),"
        "  useful INTEGER DEFAULT 0, dead INTEGER DEFAULT 0, updated REAL);"
        "INSERT INTO page_overlay(page, status) "
        "  VALUES ('concepts/velha.md', 'contested');")
    raw.execute("UPDATE _meta SET value=? WHERE key='schema_version'",
                (str(SCHEMA_VERSIONS["index.db"] - 1),))
    raw.commit(); raw.close()
    reset_initialized()
    idx = connect(db)
    row = idx.execute("SELECT status FROM page_overlay "
                      "WHERE page='concepts/velha.md'").fetchone()
    idx.close()
    assert row["status"] == "low_yield"


def test_fila_oferece_low_yield_com_rotulo_honesto(settings, kb):
    from llmwiki.usecases.plan_attention import gap_items
    _write(settings, kb,
           _doc("concepts/beco.md", "Beco", "# Beco\n\nsempre dá em nada."))
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO page_overlay(page, status) "
                "VALUES ('concepts/beco.md', 'low_yield')")
    idx.commit(); idx.close()
    items = [i for i in gap_items(settings)
             if i["target"] == "concepts/beco.md"]
    assert items and items[0]["kind"] == "low_yield"
    razao = items[0]["reason"].lower()
    assert "disputa" not in razao and "contestada" not in razao
    assert "beco" in razao or "rendimento" in razao


def test_politica_cognitiva_aceita_chave_legada(settings):
    """`allow_contested` vive em snapshots PERSISTIDOS (cognitive.db).
    A chave nova governa; a legada é traduzida, nunca recusada."""
    from llmwiki.cognitive.policy import validate_policy
    p = validate_policy({"gates": {"allow_contested": False}})
    assert p["gates"]["allow_low_yield"] is False
    p2 = validate_policy({"gates": {"allow_low_yield": True}})
    assert p2["gates"]["allow_low_yield"] is True
