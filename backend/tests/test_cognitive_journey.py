"""v0.19 — jornada ponta a ponta pela API: tema → projeção → working set
→ sessão → tentativa → feedback → agenda → suspensão → retomada. E a
regressão epistemológica: NADA disso altera o canônico."""
from __future__ import annotations
import hashlib
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": "t"})
        yield c


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _seed(settings, kb):
    BundleWriter(kb).write([
        _doc("concepts/event-sourcing.md", "Event Sourcing",
             "# ES\n\nEstado como log de eventos; ver "
             "[CQRS](/concepts/cqrs.md) e [Kafka](/concepts/kafka.md); "
             "antes [v1](/concepts/es-v1.md), detalhes em "
             "[segredo](/concepts/segredo.md); aberta: "
             "[quando não usar](/questions/es-quando-nao.md)."),
        _doc("concepts/cqrs.md", "CQRS",
             "# CQRS\n\nSeparar escrita de leitura. " + "palavra " * 300),
        _doc("concepts/kafka.md", "Kafka", "# Kafka\n\nLog distribuído."),
        _doc("concepts/es-v1.md", "ES antigo", "# Velho\n\nsubstituído.",
             superseded_by="concepts/event-sourcing.md"),
        _doc("concepts/segredo.md", "Segredo", "# S\n\nCPF etc.",
             sensitive_data=True),
        _doc("questions/es-quando-nao.md", "Quando NÃO usar ES?",
             "# Aberta\n\npendente.", type="question"),
    ], log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)


def _bundle_fingerprint(kb) -> str:
    digest = hashlib.sha256()
    for p in sorted((kb / "bundle").rglob("*.md")):
        digest.update(p.read_bytes())
    return digest.hexdigest()


def _index_fingerprint(settings) -> tuple:
    idx = connect(settings.app_support / "index.db")
    edges = idx.execute("SELECT COUNT(*) c FROM graph_edges").fetchone()["c"]
    chunks = idx.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    idx.close()
    return edges, chunks


def test_full_journey_preserves_canonical_memory(client, settings, kb):
    _seed(settings, kb)
    before_bundle = _bundle_fingerprint(kb)
    before_index = _index_fingerprint(settings)

    # 1–4: objetivo com profundidade multidimensional
    goal = client.post("/cognitive/goals", json={
        "title": "Dominar Event Sourcing", "root": "concepts/event-sourcing.md",
        "intent": "apply", "priority": 4, "horizon_days": 45,
        "time_available_min": 60,
        "depth_desired": {"conceptual": 2, "technical": 3, "practical": 2},
    })
    assert goal.status_code == 200
    goal_id = goal.json()["id"]
    assert goal.json()["_links"]["project"]["href"] == "/cognitive/projections"
    assert client.post("/cognitive/goals", json={
        "title": "x", "root": "concepts/nao-existe.md"}).status_code == 404

    # 5–11: projeção — gates + score decomposto + orçamento
    proj = client.post("/cognitive/projections",
                       json={"goal_id": goal_id}).json()
    ws = proj["working_set"]
    pages = [i["page"] for i in ws["items"]]
    assert pages[0] == "concepts/event-sourcing.md"
    assert "concepts/es-v1.md" not in pages          # superseded: gate
    assert "concepts/segredo.md" not in pages        # sensível: gate
    refused = {e["page"]: e["refused"] for e in ws["excluded_by_gate"]}
    assert any("superseded" in r for r in refused["concepts/es-v1.md"])
    assert ws["open_questions"][0]["page"] == "questions/es-quando-nao.md"
    assert all(i["components"] and i["reasons"] for i in ws["items"])
    assert proj["trace_id"]

    # 12: revisar a projeção (excluir nó) ⇒ NOVA projeção sem o nó
    proj2 = client.post("/cognitive/projections", json={
        "goal_id": goal_id, "exclude": "concepts/kafka.md"}).json()
    assert "concepts/kafka.md" not in \
        [i["page"] for i in proj2["working_set"]["items"]]
    assert proj2["id"] != proj["id"]                 # versões imutáveis

    # 13–14: sessão
    session = client.post("/cognitive/sessions", json={
        "projection_id": proj["id"], "mode": "understand"}).json()
    sid = session["id"]
    assert session["state"] == "active"
    assert session["current_item"] == "concepts/event-sourcing.md"
    assert "suspend" in session["_links"]

    # 15–19: recuperação ativa com confiança ANTES; falha confiante
    bad = client.post(f"/cognitive/sessions/{sid}/attempts", json={
        "item": "concepts/cqrs.md", "exercise": "explain",
        "confidence_before": 0.9, "result": "failure",
        "answer": "expliquei errado"})
    assert bad.status_code == 200
    assert bad.json()["review"]["interval_days"] == 0.5   # sobreconfiança
    assert bad.json()["calibration_gap"] == pytest.approx(0.9)
    ok = client.post(f"/cognitive/sessions/{sid}/attempts", json={
        "item": "concepts/event-sourcing.md", "exercise": "explain",
        "confidence_before": 0.6, "result": "success"})
    assert ok.json()["accessibility"]["level"] == "explanation"
    assert client.post(f"/cognitive/sessions/{sid}/attempts", json={
        "item": "concepts/fora.md", "exercise": "recall",
        "confidence_before": 0.5, "result": "success"}).status_code == 400

    # feedback imutável e tipado
    assert client.post(f"/cognitive/sessions/{sid}/feedback", json={
        "scope": "concept", "target": "concepts/cqrs.md",
        "verdict": "too_shallow"}).status_code == 200
    assert client.post(f"/cognitive/sessions/{sid}/feedback", json={
        "scope": "concept", "verdict": "genial"}).status_code == 400

    # 21–22: suspender → cápsula → retomar
    suspended = client.post(f"/cognitive/sessions/{sid}/suspend", json={
        "reason": "fim do horário", "next_step": "aplicar num exemplo"})
    capsule = suspended.json()["capsule"]
    assert capsule["next_step"] == "aplicar num exemplo"
    assert capsule["open_questions"] == ["questions/es-quando-nao.md"]
    assert client.post(f"/cognitive/sessions/{sid}/suspend",
                       json={}).status_code == 409
    resumed = client.post(f"/cognitive/sessions/{sid}/resume").json()
    assert resumed["state"] == "active"
    assert resumed["capsule"]["next_step"] == "aplicar num exemplo"
    done = client.post(f"/cognitive/sessions/{sid}/complete").json()
    assert done["state"] == "completed"

    # 23: agenda — a falha confiante venceu (0.5d... ainda não devida);
    # força vencimento e completa
    cog = connect(settings.app_support / "cognitive.db")
    cog.execute("UPDATE review_schedules SET due_at = due_at - 3*86400")
    cog.commit(); cog.close()
    due = client.get("/cognitive/reviews/due").json()["reviews"]
    assert {r["item"] for r in due} == {"concepts/cqrs.md",
                                        "concepts/event-sourcing.md"}
    review_id = due[0]["id"]
    assert client.post(
        f"/cognitive/reviews/{review_id}/complete").status_code == 200
    assert client.post(
        f"/cognitive/reviews/{review_id}/complete").status_code == 404

    # 24: observabilidade — eventos do canal cognitive no runtime.db
    rt = connect(settings.app_support / "runtime.db")
    types = {r["type"] for r in rt.execute(
        "SELECT type FROM events WHERE channel='cognitive'")}
    rt.close()
    assert {"focus.goal.created", "focus.projection.generated",
            "focus.node.suppressed", "cognitive.session.started",
            "retrieval.attempted", "review.scheduled",
            "cognitive.session.suspended", "cognitive.session.resumed",
            "cognitive.session.completed", "feedback.recorded",
            "review.completed"} <= types

    # 20/18.5: REGRESSÃO EPISTEMOLÓGICA — canônico intacto byte a byte
    assert _bundle_fingerprint(kb) == before_bundle
    assert _index_fingerprint(settings) == before_index
    # e a falha de recuperação NÃO mexeu na confiança epistemológica
    from llmwiki.okf.bundle import BundleReader
    doc = BundleReader(kb / "bundle").load("concepts/cqrs.md")
    meta = doc.meta.model_dump(exclude_none=True)
    assert "confidence" not in meta or meta["confidence"] != "ambiguous"
    cog = connect(settings.app_support / "cognitive.db")
    level = cog.execute("SELECT level, streak FROM accessibility "
                        "WHERE item='concepts/cqrs.md'").fetchone()
    cog.close()
    assert level["streak"] == 0            # a falha mora AQUI, não no bundle


def test_declared_profile_beats_inferred_in_journey(client, settings, kb):
    """Invariante §18.2: perfil declarado vence preferência inferida —
    já garantido no /ask (v0.18); aqui, a política declarada da projeção
    vence o default."""
    _seed(settings, kb)
    goal_id = client.post("/cognitive/goals", json={
        "title": "t", "root": "concepts/event-sourcing.md"}).json()["id"]
    tight = client.post("/cognitive/projections", json={
        "goal_id": goal_id,
        "policy": {"budgets": {"max_items": 1}}}).json()
    assert len(tight["working_set"]["items"]) == 1
    assert tight["working_set"]["budgets"]["max_items"] == 1
    bad = client.post("/cognitive/projections", json={
        "goal_id": goal_id, "policy": {"weights": {"mistica": 1}}})
    assert bad.status_code == 400
