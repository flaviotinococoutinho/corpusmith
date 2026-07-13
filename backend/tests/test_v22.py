"""v0.22 — reference.db: referência determinística do mundo, relacional
e separada; precedência authority_record > ref_* > seeds no gazetteer;
verificador de citação mal-atribuída."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.okf.authorities import invalidate_cache, load_gazetteer
from llmwiki.okf.bundle import BundleReader
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.normalize import analyze
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue
from llmwiki.usecases.manage_reference import (ImportReferenceData,
                                               check_quotation,
                                               reference_stats,
                                               seed_reference)


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": "t"})
        yield c


def test_seed_is_idempotent_and_never_overwrites_user_data(settings):
    seed_reference(settings)
    first = reference_stats(settings)
    assert first["ref_terms"] >= 4 and first["ref_quotations"] >= 3
    # usuário corrige um registro; o seed seguinte NÃO pode desfazer
    ImportReferenceData(settings, {"terms": [
        {"canonical": "Donald Knuth", "kind": "person",
         "aliases": ["knuth", "professor knuth"]}]}).execute()
    seed_reference(settings)
    ref = connect(settings.app_support / "reference.db")
    aliases = ref.execute("SELECT aliases FROM ref_terms WHERE "
                          "canonical='Donald Knuth'").fetchone()["aliases"]
    ref.close()
    assert "professor knuth" in aliases
    assert reference_stats(settings)["ref_terms"] == first["ref_terms"]


def test_import_validates_shapes(settings):
    with pytest.raises(ValueError):
        ImportReferenceData(settings, {"terms": [{"kind": "person"}]}).execute()
    with pytest.raises(ValueError):
        ImportReferenceData(settings, {"facts": [
            {"kind": "teorema", "name": "x", "statement": "y"}]}).execute()
    with pytest.raises(ValueError):
        ImportReferenceData(settings, {"quotations": [
            {"quote": "sem autor"}]}).execute()


def test_gazetteer_precedence_authority_beats_reference(settings, kb):
    seed_reference(settings)
    invalidate_cache()
    reader = BundleReader(kb / "bundle")
    # 1) só reference.db: alias "dijkstra" canonicaliza pelo ref_term
    report = analyze("dijkstra provou isso.", gaz=load_gazetteer(reader))
    assert any(m.canonical == "Edsger W. Dijkstra" for m in report.matches)
    # 2) authority_record no bundle VENCE a referência do mundo
    BundleWriter(kb).write(
        [OKFDocument(rel_path="authorities/dijkstra.md",
                     body="# Dijkstra\n\ncuradoria local.",
                     meta=OKFFrontMatter(
                         type="authority_record", title="Dijkstra",
                         privacy="local_only",
                         **{"canonical": "Edsger Wybe Dijkstra",
                            "aliases": ["dijkstra"]}))],
        log_kind="Creation", log_message="m", commit_message="c")
    invalidate_cache()
    report = analyze("dijkstra provou isso.", gaz=load_gazetteer(reader))
    canonicals = {m.canonical for m in report.matches}
    assert "Edsger Wybe Dijkstra" in canonicals        # autoridade venceu
    assert "Edsger W. Dijkstra" not in canonicals


def test_quotation_check_flags_misattribution(settings):
    seed_reference(settings)
    text = ('Como disse Linus Torvalds: "Program testing can be used to '
            'show the presence of bugs, but never to show their absence!"')
    result = check_quotation(settings, text, claimed_author="Linus Torvalds")
    assert result["misattributions"]
    wrong = result["misattributions"][0]
    assert wrong["author"] == "Edsger W. Dijkstra"     # o autor correto
    assert "1970" in wrong["source"]
    # autor certo ⇒ match sem má-atribuição
    ok = check_quotation(settings, text, claimed_author="E. W. Dijkstra")
    assert ok["matches"] and not ok["misattributions"]
    # texto sem citação conhecida ⇒ vazio
    assert check_quotation(settings, "nada aqui")["matches"] == []


def test_reference_http_contract(client):
    stats = client.get("/cockpit/reference").json()
    assert stats["ref_facts"] >= 4                      # seed no mount
    assert any(f["name"] == "Teorema CAP" for f in stats["facts"])
    ok = client.post("/cockpit/reference", json={"facts": [
        {"kind": "law", "name": "Lei de Amdahl",
         "statement": "S = 1/((1−p)+p/n)", "domain": "paralelismo"}]})
    assert ok.status_code == 200 and ok.json()["facts"] == 1
    assert client.post("/cockpit/reference", json={"facts": [
        {"kind": "chute", "name": "x", "statement": "y"}]}).status_code == 400
    check = client.post("/cockpit/reference/check", json={
        "text": "Talk is cheap. Show me the code.",
        "author": "Bill Gates"}).json()
    assert check["misattributions"][0]["author"] == "Linus Torvalds"


def test_lint_flags_unattributed_known_quotation(settings, kb, runner):
    """v1.2: porta do ADR-32 fechada — lint de corpus com custo medido."""
    import time as _time
    seed_reference(settings)
    invalidate_cache()
    quote = ("Program testing can be used to show the presence of bugs, "
             "but never to show their absence!")
    BundleWriter(kb).write([
        OKFDocument(rel_path="concepts/testes.md",
                    body=f'# Testes\n\nComo se diz: "{quote}"\n',
                    meta=OKFFrontMatter(type="concept", title="Testes",
                                        privacy="local_only")),
        OKFDocument(rel_path="concepts/testes-ok.md",
                    body=f'# Testes 2\n\nDijkstra: "{quote}"\n',
                    meta=OKFFrontMatter(type="concept", title="Testes 2",
                                        privacy="local_only")),
    ], log_kind="Creation", log_message="m", commit_message="c")
    invalidate_cache()
    started = _time.perf_counter()
    findings = runner.lint_bundle(kb / "bundle")
    elapsed = _time.perf_counter() - started
    hits = [f for f in findings.to_dicts()
            if f["rule"] == "policy.quotation_attribution"]
    assert [h["path"] for h in hits] == ["concepts/testes.md"]
    assert "Dijkstra" in hits[0]["message"]      # aponta o autor correto
    assert elapsed < 2.0                          # custo medido: trivial


def test_inv003_superseded_out_of_default_retrieval(settings, kb):
    """INV-003 (v1.3): substituída NÃO participa da recuperação padrão;
    com as_of histórico, a partição bi-temporal decide e a evidência
    carrega a marca."""
    from llmwiki.facades import MemoryFacade
    from llmwiki.retrieval.fts import rebuild_index as _rb
    BundleWriter(kb).write([
        OKFDocument(rel_path="concepts/porta-v1.md",
                    body="# Porta\n\nporta do daemon era 9000.",
                    meta=OKFFrontMatter(
                        type="concept", title="Porta v1",
                        privacy="local_only",
                        valid_at="2024-01-01T00:00:00+00:00",
                        invalid_at="2025-01-01T00:00:00+00:00",
                        **{"superseded_by": "concepts/porta-v2.md"})),
        OKFDocument(rel_path="concepts/porta-v2.md",
                    body="# Porta\n\nporta do daemon agora 8377.",
                    meta=OKFFrontMatter(type="concept", title="Porta v2",
                                        privacy="local_only",
                                        valid_at="2025-01-01T00:00:00+00:00")),
    ], log_kind="Creation", log_message="m", commit_message="c")
    _rb(settings)
    r = MemoryFacade(settings).ask("porta do daemon", local_only=True)
    pages = [e["page"] for e in r["evidence"]]
    assert "concepts/porta-v2.md" in pages
    assert "concepts/porta-v1.md" not in pages     # filtro DURO no default
    hist = MemoryFacade(settings).ask("porta do daemon",
                                      local_only=True, as_of="2024-06-01")
    v1 = next(e for e in hist["evidence"]
              if e["page"] == "concepts/porta-v1.md")
    assert v1["superseded"] is True                # histórico legítimo, marcado


def test_inv002_index_generation_change_forces_full_rebuild(settings, kb):
    from llmwiki.retrieval import fts
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/a.md", body="# A\n\ncorpo.",
                     meta=OKFFrontMatter(type="concept", title="A",
                                         privacy="local_only"))],
        log_kind="Creation", log_message="m", commit_message="c")
    fts.rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    meta = {r["key"]: r["value"] for r in
            idx.execute("SELECT key, value FROM index_meta")}
    idx.close()
    assert meta["index_generation"] == fts.INDEX_GENERATION
    assert len(meta.get("bundle_head", "")) == 40   # sha do HEAD carimbado
    # bump de geração ⇒ full mesmo sem NENHUM arquivo mudar
    idx = connect(settings.app_support / "index.db")
    idx.execute("UPDATE index_meta SET value='g0:antiga' "
                "WHERE key='index_generation'")
    idx.commit(); idx.close()
    result = fts.rebuild_index(settings)
    assert result["mode"] == "full"
