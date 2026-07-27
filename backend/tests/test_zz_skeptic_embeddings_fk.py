"""CETICO: tenta REFUTAR o achado da FK embeddings->chunks."""
from __future__ import annotations
import sqlite3
import pytest
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.usecases.diagnose import DiagnoseSystem


def _doc(body="# ES\n\neventos e coisas."):
    return OKFDocument(rel_path="concepts/es.md", body=body,
                       meta=OKFFrontMatter(type="concept", title="ES",
                                           privacy="local_only"))


def _seed_with_embedding(settings, kb):
    BundleWriter(kb).write([_doc()], log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    fk = idx.execute("PRAGMA foreign_keys").fetchone()[0]
    cid = idx.execute("SELECT id FROM chunks LIMIT 1").fetchone()["id"]
    idx.execute("INSERT INTO embeddings(chunk_id,model,vec) VALUES (?,?,?)",
                (cid, "nomic", b"v"))
    idx.commit()
    n = idx.execute("SELECT COUNT(*) c FROM embeddings").fetchone()["c"]
    idx.close()
    print(f"[seed] foreign_keys={fk} chunk_id={cid} embeddings={n}")
    return cid


def test_a_reescrever_pagina_e_reindexar(settings, kb):
    _seed_with_embedding(settings, kb)
    BundleWriter(kb).write([_doc("# ES\n\nCORPO NOVO totalmente diferente.")],
                           log_kind="Update", log_message="m2",
                           commit_message="c2")
    with pytest.raises(sqlite3.IntegrityError) as e:
        rebuild_index(settings)
    print(f"[a] {type(e.value).__name__}: {e.value}")


def test_b_rebuild_full(settings, kb):
    _seed_with_embedding(settings, kb)
    with pytest.raises(sqlite3.IntegrityError) as e:
        rebuild_index(settings, full=True)
    print(f"[b] {type(e.value).__name__}: {e.value}")


def test_c_doctor_repair(settings, kb):
    _seed_with_embedding(settings, kb)
    # forca um achado reparavel: apaga chunks de uma pagina existente?
    # primeiro veja o que o doctor acha sem forcar
    r0 = DiagnoseSystem(settings, repair=True).execute()
    print(f"[c-sem-forcar] repaired={r0.get('repaired')} "
          f"findings={[f['inv'] for f in r0.get('findings', [])]}")
    # forca INV-002: index_generation antiga
    idx = connect(settings.app_support / "index.db")
    idx.execute("UPDATE index_meta SET value='g0:velha' "
                "WHERE key='index_generation'")
    idx.commit()
    idx.close()
    try:
        r = DiagnoseSystem(settings, repair=True).execute()
        print(f"[c-forcado] SEM EXCECAO repaired={r.get('repaired')} "
              f"findings={[f['inv'] for f in r.get('findings', [])]}")
    except sqlite3.IntegrityError as e:
        print(f"[c-forcado] IntegrityError: {e}")
        raise


def test_d_bump_generation(settings, kb):
    _seed_with_embedding(settings, kb)
    idx = connect(settings.app_support / "index.db")
    idx.execute("UPDATE index_meta SET value='g3:antiga' "
                "WHERE key='index_generation'")
    idx.commit()
    idx.close()
    with pytest.raises(sqlite3.IntegrityError) as e:
        rebuild_index(settings)
    print(f"[d] {type(e.value).__name__}: {e.value}")


def test_e_incremental_sem_mudanca(settings, kb):
    """Controle: reindex sem nada mudado NAO deve estourar."""
    _seed_with_embedding(settings, kb)
    r = rebuild_index(settings)
    print(f"[e-controle] ok: {r['mode']}/{r['delta']} "
          f"reindexed={r['reindexed']}")
