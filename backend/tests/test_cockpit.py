"""Cockpit end-to-end (§9): promote cria página + log + commit + evento;
qualidade == lint_bundle; auth por header OU ?auth=."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue

TOKEN = "test-token"


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    connect(settings.app_support / "index.db").close()
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": TOKEN})
        yield c


def test_auth_header_or_query(client):
    assert client.get("/cockpit/dashboard",
                      headers={"x-llmwiki-auth": "errado"}).status_code == 401
    assert client.get(f"/cockpit/dashboard?auth={TOKEN}",
                      headers={"x-llmwiki-auth": "errado"}).status_code == 200


def test_promote_creates_page_log_commit_event(client, kb, settings):
    r = client.post("/cockpit/promote", json={
        "kind": "decision", "title": "Usar filas locais",
        "content": "Decidimos processar tudo em fila local.",
        "source": "chat:2026-07-05", "privacy": "local_only"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pages"] == ["decisions/usar-filas-locais.md"]
    assert data["commit"]
    log = (kb / "bundle/log.md").read_text()
    assert "[Creation] promovido de chat:2026-07-05: Usar filas locais" in log
    rt = connect(settings.app_support / "runtime.db")
    events = [dict(r) for r in rt.execute(
        "SELECT type FROM events ORDER BY seq DESC LIMIT 5")]
    rt.close()
    assert any(e["type"] == "memory.promoted" for e in events)
    # promoção humana: sem source_sha256 e mesmo assim aceita (§9)
    raw = (kb / "bundle/decisions/usar-filas-locais.md").read_text()
    assert "source_sha256" not in raw
    assert "generated_via: human:promote" in raw


def test_promote_invalid_kind_is_400(client):
    r = client.post("/cockpit/promote",
                    json={"kind": "nada", "title": "x", "content": "y"})
    assert r.status_code == 400


def test_quality_matches_cli_lint_on_clean_bundle(client):
    q = client.get("/cockpit/quality").json()
    assert q["errors"] == 0
    assert q["pages"] == 0


def test_quality_reports_raw_parse_failures(client, kb):
    (kb / "bundle/concepts").mkdir(exist_ok=True)
    (kb / "bundle/concepts/solto.md").write_text("# sem frontmatter\n")
    q = client.get("/cockpit/quality").json()
    assert q["errors"] == 1
    rules = {f["rule"] for f in q["findings"]}
    assert "okf.frontmatter_missing" in rules


def test_dashboard_and_pages_after_promote(client):
    client.post("/cockpit/promote", json={
        "kind": "semantic", "title": "Memória agêntica",
        "content": "conceito", "privacy": "local_only"})
    d = client.get("/cockpit/dashboard").json()
    assert d["pages"] == 1
    pages = client.get("/cockpit/pages").json()["pages"]
    assert pages[0]["path"] == "concepts/memoria-agentica.md"
    page = client.get("/cockpit/page",
                      params={"path": pages[0]["path"]}).json()
    assert page["meta"]["generated_via"] == "human:promote"
    assert page["git"]                       # histórico do git presente


def test_mark_stale_roundtrip(client):
    client.post("/cockpit/promote", json={
        "kind": "semantic", "title": "Antigo",
        "content": "x", "privacy": "local_only"})
    r = client.post("/cockpit/page/stale",
                    json={"path": "concepts/antigo.md"})
    assert r.status_code == 200, r.text
    page = client.get("/cockpit/page",
                      params={"path": "concepts/antigo.md"}).json()
    assert page["meta"]["stale_as_of"]


def test_memory_layers_shape(client):
    m = client.get("/cockpit/memory").json()
    assert set(m) == {"working", "episodic", "semantic", "procedural"}


def test_review_compute_is_side_effect_free(client, kb):
    before = sorted(p.name for p in (kb / "bundle").rglob("*.md"))
    r = client.get("/cockpit/review")
    assert r.status_code == 200
    assert set(r.json()) >= {"week", "new_pages", "orphans", "stale",
                             "decisions", "questions", "top_tags"}
    after = sorted(p.name for p in (kb / "bundle").rglob("*.md"))
    assert before == after
