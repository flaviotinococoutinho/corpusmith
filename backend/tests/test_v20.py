"""v0.20 — profundidade validada por dimensão, experiências
metacognitivas declaradas, analogias com gate de promoção,
CurationProjection e métricas cognitivas."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.cognitive.progress import (depth_progress, exercise_prompt,
                                        new_analogy)
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


# ------------------------------------------------------------ domínio puro
def test_depth_progress_validates_only_with_instruments():
    desired = {"conceptual": 2, "transfer": 3, "historical": 2}
    progress = depth_progress(desired, [
        {"exercise": "explain", "level": "explanation"},   # conceptual → 2
        {"exercise": "transfer", "level": "transfer"},     # transfer → 3
    ])
    assert progress["conceptual"] == {"desired": 2, "validated": 2,
                                      "measurable": True, "progress": 1.0}
    assert progress["transfer"]["progress"] == 1.0
    assert progress["historical"]["measurable"] is False   # sem instrumento
    assert progress["historical"]["validated"] is None
    assert "practical" not in progress                     # não desejada


def test_analogy_contract_requires_breaks():
    with pytest.raises(ValueError, match="QUEBRA"):
        new_analogy(analogy_id="a1", source="fila", target="pipeline",
                    mappings=["item↔job"])
    a = new_analogy(analogy_id="a1", source="fila", target="pipeline",
                    mappings=["item↔job"], breaks=["fila não tem estágios"])
    assert a["status"] == "draft" and a["origin"] == "human"


def test_exercise_prompts_are_deterministic():
    assert "Explique «CQRS»" in exercise_prompt("explain", "CQRS")
    assert exercise_prompt("recall", "X") == exercise_prompt("recall", "X")
    with pytest.raises(ValueError):
        exercise_prompt("meditar", "X")


# ------------------------------------------------------------ jornada HTTP
def test_v20_endpoints_full_flow(client, settings, kb):
    from llmwiki.okf.document import OKFDocument, OKFFrontMatter
    from llmwiki.okf.writer import BundleWriter
    from llmwiki.retrieval.fts import rebuild_index
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/es.md",
                     body="# ES\n\nlog de eventos.",
                     meta=OKFFrontMatter(type="concept", title="ES",
                                         privacy="local_only"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    gid = client.post("/cognitive/goals", json={
        "title": "t", "root": "concepts/es.md",
        "depth_desired": {"conceptual": 2, "practical": 2}}).json()["id"]
    pid = client.post("/cognitive/projections",
                      json={"goal_id": gid}).json()["id"]
    sid = client.post("/cognitive/sessions",
                      json={"projection_id": pid}).json()["id"]
    for exercise in ("explain", "apply"):
        client.post(f"/cognitive/sessions/{sid}/attempts", json={
            "item": "concepts/es.md", "exercise": exercise,
            "confidence_before": 0.7, "result": "success"})

    # profundidade validada por prática
    progress = client.get(f"/cognitive/goals/{gid}/progress").json()
    assert progress["depth"]["conceptual"]["validated"] >= 2
    assert progress["depth"]["practical"]["progress"] == 1.0

    # experiência metacognitiva declarada (evento, não diagnóstico)
    ok = client.post("/cognitive/experiences", json={
        "session_id": sid, "item": "concepts/es.md",
        "type": "familiar_cannot_explain", "intensity": 4})
    assert ok.status_code == 200 and ok.json()["id"]
    assert client.post("/cognitive/experiences", json={
        "type": "telepatia"}).status_code == 400

    # analogia: recusa sem ruptura; registro; promoção via gate humano
    assert client.post("/cognitive/analogies", json={
        "source": "ES", "target": "extrato bancário",
        "mappings": ["evento↔lançamento"]}).status_code == 400
    aid = client.post("/cognitive/analogies", json={
        "source": "ES", "target": "extrato bancário",
        "mappings": ["evento↔lançamento", "estado↔saldo"],
        "breaks": ["extrato não reprocessa o passado"],
        "didactic_goal": "intuição inicial"}).json()["id"]
    assert client.get("/cognitive/analogies").json()[
        "analogies"][0]["id"] == aid
    promoted = client.post(f"/cognitive/analogies/{aid}/promote").json()
    assert promoted["page"].startswith("concepts/")
    page = client.get(f"/cockpit/page?path={promoted['page']}").json()
    assert "QUEBRA" in page["body"]                # limites vão no corpo
    assert page["meta"]["generated_via"] == "human:promote"

    # métricas computadas
    metrics = client.get("/cognitive/metrics").json()
    assert metrics["attempts"] == 2
    assert metrics["application_success_rate"] == 1.0
    assert metrics["brier"] is not None
    assert metrics["review_completion"]["due"] >= 1

    # prompt determinístico via API
    prompt = client.get("/cognitive/prompt",
                        params={"exercise": "transfer", "title": "ES"}).json()
    assert "transferência" in prompt["prompt"]


def test_curation_projection_is_read_only_and_aligned(client, settings, kb):
    from llmwiki.okf.document import OKFDocument, OKFFrontMatter
    from llmwiki.okf.writer import BundleWriter
    from llmwiki.retrieval.fts import rebuild_index
    BundleWriter(kb).write([
        OKFDocument(rel_path="concepts/alvo.md", body="# A\n\ncorpo.",
                    meta=OKFFrontMatter(type="concept", title="Alvo",
                                        privacy="local_only",
                                        stale_as_of="abc1234")),
        OKFDocument(rel_path="questions/duvida.md", body="# D\n\n?",
                    meta=OKFFrontMatter(type="question", title="Dúvida",
                                        privacy="local_only")),
    ], log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    client.post("/cognitive/goals", json={
        "title": "t", "root": "concepts/alvo.md"})
    cur = client.get("/cognitive/curation").json()
    by_page = {i["page"]: i for i in cur["items"]}
    assert by_page["concepts/alvo.md"]["aligned_with_focus"] is True
    assert "stale" in by_page["concepts/alvo.md"]["signals"]
    assert by_page["questions/duvida.md"]["aligned_with_focus"] is False
    assert all(i["reason"] for i in cur["items"])
    # leitura pura: nada mudou no canônico
    from llmwiki.okf.bundle import BundleReader
    meta = BundleReader(kb / "bundle").load("concepts/alvo.md") \
        .meta.model_dump(exclude_none=True)
    assert meta["stale_as_of"] == "abc1234"
