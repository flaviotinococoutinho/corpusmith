"""Base fria (v0.12): gates ACT-R/TMS de esquecimento, compactação MDL,
recall de fallback e reciclagem (manual, automática e via reconciliador)."""
from __future__ import annotations
import time
import pytest
from corpusmith.facades import CompilerFacade, CurationFacade
from corpusmith.kernel.activation import retrieval_probability
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.usecases.cold_memory import (FreezeMemory, FreezeVeto,
                                          RecycleMemory, cold_search)
from corpusmith.usecases.ask_memory import AskMemory


def _doc(rel="concepts/x.md", body="# X\n\ncorpo", **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body, meta=OKFFrontMatter(**meta))


def _write(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _make_idle(settings, page, *, days=200):
    """Simula memória ociosa: 1 leitura antiga, vida longa ⇒ P(recall)≈0."""
    rt = connect(settings.app_support / "runtime.db")
    old = time.time() - days * 86_400
    rt.execute("INSERT OR REPLACE INTO page_heat"
               "(path, reads, last_seen, first_seen) VALUES (?,1,?,?)",
               (page, old, old - 86_400))
    rt.commit()
    rt.close()


# ---------------------------------------------------------------- kernel
def test_retrieval_probability_properties():
    assert retrieval_probability(float("-inf")) == 0.0
    assert abs(retrieval_probability(0.0, tau=0.0) - 0.5) < 1e-9  # B=τ ⇒ 0.5
    assert retrieval_probability(2.0) > retrieval_probability(-2.0)
    # ruído maior achata a curva em direção a 0.5
    sharp = retrieval_probability(1.0, noise=0.1)
    flat = retrieval_probability(1.0, noise=2.0)
    assert sharp > flat > 0.5


# ------------------------------------------------------- gates de veto
def test_freeze_vetoes(settings, kb):
    page = _doc(rel="concepts/ativa.md", title="Ativa",
                body="# Ativa\n\nusada o tempo todo")
    protected = _doc(rel="authorities/stack/duckdb.md",
                     type="authority_record", title="DuckDB",
                     canonical="DuckDB", aliases=["duckdb"], authority="stack")
    base = _doc(rel="concepts/citada.md", title="Citada",
                body="# Citada\n\nfato base")
    citer = _doc(rel="concepts/citadora.md", title="Citadora",
                 body="# Citadora\n\nver [citada](/concepts/citada.md)")
    _write(settings, kb, page, protected, base, citer)

    # tipo protegido nunca congela (nem com force)
    with pytest.raises(FreezeVeto, match="protegido"):
        FreezeMemory(settings, "authorities/stack/duckdb.md",
                     force=True).execute()
    # dependentes vetam (TMS) — nem com force
    with pytest.raises(FreezeVeto, match="dependem"):
        FreezeMemory(settings, "concepts/citada.md", force=True).execute()
    # página quente: leituras recentes ⇒ P(recall) alto ⇒ veto
    rt = connect(settings.app_support / "runtime.db")
    now = time.time()
    rt.execute("INSERT OR REPLACE INTO page_heat"
               "(path, reads, last_seen, first_seen) VALUES (?,50,?,?)",
               ("concepts/ativa.md", now, now - 7 * 86_400))
    rt.commit()
    rt.close()
    with pytest.raises(FreezeVeto, match="recall"):
        FreezeMemory(settings, "concepts/ativa.md").execute()
    # force (gesto humano) dispensa o gate de ativação, não os estruturais
    result = FreezeMemory(settings, "concepts/ativa.md", force=True).execute()
    assert result["frozen"] is True


def test_freeze_compacts_and_recycle_restores_byte_identical(settings, kb):
    body = "# Fato antigo\n\n" + ("detalhe repetitivo do protocolo. " * 80)
    page = _doc(rel="concepts/fato-antigo.md", title="Fato antigo",
                description="protocolo legado", body=body)
    _write(settings, kb, page)
    _make_idle(settings, "concepts/fato-antigo.md")
    original = (kb / "bundle/concepts/fato-antigo.md").read_text()

    result = CurationFacade(settings).freeze("concepts/fato-antigo.md")
    assert result["recall_p"] < 0.05
    assert not (kb / "bundle/concepts/fato-antigo.md").exists()  # saiu do quente
    stats = CurationFacade(settings).cold()
    assert stats["count"] == 1
    assert stats["compression_saved"] > 50          # MDL: corpo repetitivo comprime
    assert "Freeze" in (kb / "bundle/log.md").read_text()
    # recall de fallback acha pelo digest
    assert cold_search(settings, "protocolo legado")[0]["page"] == \
        "concepts/fato-antigo.md"

    thawed = CurationFacade(settings).recycle("concepts/fato-antigo.md")
    assert thawed["recycled"] and thawed["times"] == 1
    restored = (kb / "bundle/concepts/fato-antigo.md").read_text()
    assert body.strip() in restored                  # corpo intacto
    assert "recycled: 1" in restored                 # carrega a própria história
    assert CurationFacade(settings).cold()["count"] == 0
    # e o conteúdo original segue byte-compatível fora do frontmatter novo
    assert original.split("---")[2].strip() in restored


def test_ask_fallback_surfaces_and_auto_recycles(settings, kb):
    page = _doc(rel="concepts/zeppelin.md", title="Dirigível Zeppelin",
                description="história do dirigível zeppelin",
                body="# Zeppelin\n\nO dirigível zeppelin cruzava o Atlântico.")
    _write(settings, kb, page)
    _make_idle(settings, "concepts/zeppelin.md")
    CurationFacade(settings).freeze("concepts/zeppelin.md")

    # sem auto_recycle: abstém, mas aponta a memória fria compatível
    r = AskMemory(settings, "o que sabemos do dirigível zeppelin?",
                  local_only=True).execute()
    assert r["abstained"] is True
    assert r["cold_matches"][0]["page"] == "concepts/zeppelin.md"
    assert any("FRIA" in g for g in r["gaps"])

    # com auto_recycle: reidrata e responde na mesma consulta
    s2 = settings.with_overrides(memory={"auto_recycle": True})
    r2 = AskMemory(s2, "o que sabemos do dirigível zeppelin?",
                   local_only=True).execute()
    assert r2["abstained"] is False
    assert any(e["page"] == "concepts/zeppelin.md" for e in r2["evidence"])
    assert (kb / "bundle/concepts/zeppelin.md").exists()


def test_reconciler_recycles_frozen_memory_on_matching_source(settings, kb):
    page = _doc(rel="concepts/paper-frio.md", title="Paper frio",
                body="# Paper\n\nEstudo com doi 10.5555/99999 sobre cache.")
    _write(settings, kb, page)
    _make_idle(settings, "concepts/paper-frio.md")
    CurationFacade(settings).freeze("concepts/paper-frio.md")
    assert not (kb / "bundle/concepts/paper-frio.md").exists()

    (kb / "raw" / "novo-sobre-paper.md").write_text(
        "# Novidade\n\nRevisitando o estudo doi 10.5555/99999 com dados novos.\n")
    result = CompilerFacade(settings).compile("raw/novo-sobre-paper.md")
    assert result["op"] == "RECYCLE"
    assert result["page"] == "concepts/paper-frio.md"
    assert (kb / "bundle/concepts/paper-frio.md").exists()   # reidratada
    assert CurationFacade(settings).cold()["count"] == 0
    rt = connect(settings.app_support / "runtime.db")
    row = rt.execute("SELECT op FROM reconcile_log ORDER BY id DESC LIMIT 1"
                     ).fetchone()
    rt.close()
    assert row["op"] == "RECYCLE"                            # migração do CHECK


def test_recycle_unknown_page_raises(settings, kb):
    with pytest.raises(KeyError):
        RecycleMemory(settings, "concepts/nunca-existiu.md").execute()


def test_reconcile_log_check_migration(tmp_path):
    import sqlite3
    old = tmp_path / "runtime.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE reconcile_log(id INTEGER PRIMARY KEY, "
                 "ts REAL, candidate TEXT, "
                 "op TEXT CHECK(op IN ('ADD','UPDATE','SUPERSEDE','NOOP')), "
                 "target TEXT, reason TEXT, signals TEXT)")
    conn.execute("INSERT INTO reconcile_log(candidate, op) VALUES ('x','ADD')")
    conn.commit()
    conn.close()
    migrated = connect(old)
    migrated.execute("INSERT INTO reconcile_log(candidate, op) "
                     "VALUES ('y','RECYCLE')")          # agora aceito
    rows = migrated.execute("SELECT COUNT(*) c FROM reconcile_log").fetchone()
    migrated.close()
    assert rows["c"] == 2                                # dados preservados


@pytest.fixture
def client(settings, kb):
    from fastapi.testclient import TestClient
    from corpusmith.api.system import build_app
    from corpusmith.runtime.events import EventBus
    from corpusmith.runtime.governor import Governor
    from corpusmith.runtime.queue import JobQueue
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-corpusmith-auth": "t"})
        yield c


def test_cockpit_cold_endpoints(client, kb, settings):
    client.post("/cockpit/promote", json={
        "kind": "semantic", "title": "Velharia",
        "content": "assunto raramente usado", "privacy": "local_only"})
    from corpusmith.retrieval.fts import rebuild_index as _ri
    _ri(settings)
    _make_idle(settings, "concepts/velharia.md")
    r = client.post("/cockpit/freeze", json={"path": "concepts/velharia.md"})
    assert r.status_code == 200, r.text
    assert client.get("/cockpit/cold").json()["count"] == 1
    # congelar de novo (já fora do bundle) → 404; veto → 409
    assert client.post("/cockpit/freeze",
                       json={"path": "concepts/velharia.md"}).status_code == 404
    r = client.post("/cockpit/recycle", json={"path": "concepts/velharia.md"})
    assert r.status_code == 200 and r.json()["recycled"]
    assert client.post("/cockpit/recycle",
                       json={"path": "concepts/velharia.md"}).status_code == 404
