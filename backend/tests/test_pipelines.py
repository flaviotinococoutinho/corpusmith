"""v0.17 — pipelines configuráveis: orquestração como dado, registry por
injeção, política de erro por estágio, passagem $prev, trace/span por run
e contrato HTTP (seed builtin, salvar, rodar, filme dos runs)."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.kernel import identity
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue
from llmwiki.usecases.run_pipeline import (DEFAULT_PIPELINES, DeletePipeline,
                                           RunPipeline, SavePipeline,
                                           list_pipelines, pipeline_runs,
                                           seed_default_pipelines,
                                           validate_spec)


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": "t"})
        yield c


def _registry(calls):
    """Registry fake injetado (DIP): registra a ordem e devolve dados."""
    def ok(name, result=None):
        def handler(s, payload, emit):
            calls.append((name, payload))
            return result or {"ran": name}
        return handler

    def boom(s, payload, emit):
        calls.append(("boom", payload))
        raise RuntimeError("estágio explodiu")

    return {"a": ok("a", {"page": "concepts/x.md", "n": 3}),
            "b": ok("b"), "c": ok("c"), "boom": boom}


# ------------------------------------------------------------- validação
def test_spec_validation_rejects_bad_shapes(settings):
    with pytest.raises(ValueError):
        validate_spec("Nome Ruim!", {"stages": [{"job": "a"}]})
    with pytest.raises(ValueError):
        validate_spec("ok", {"stages": []})
    with pytest.raises(ValueError):
        validate_spec("ok", {"stages": [{"payload": {}}]})       # sem job
    with pytest.raises(ValueError):
        validate_spec("ok", {"stages": [{"job": "a", "on_error": "retry"}]})
    with pytest.raises(ValueError):                              # recursão
        validate_spec("ok", {"stages": [{"job": "pipeline"}]})


def test_run_fails_fast_on_unknown_job(settings):
    SavePipeline(settings, "quebrado",
                 {"stages": [{"job": "nao-existe"}]}).execute()
    with pytest.raises(ValueError, match="desconhecidos"):
        RunPipeline(settings, "quebrado", _registry([])).execute()
    assert pipeline_runs(settings) == []          # nada rodou pela metade


# ------------------------------------------------------------- execução
def test_stages_run_in_order_with_prev_passing(settings):
    calls = []
    SavePipeline(settings, "encadeado", {"stages": [
        {"job": "a"},
        {"job": "b", "payload": {"path": "$prev.page", "fixo": 1}},
    ]}).execute()
    result = RunPipeline(settings, "encadeado", _registry(calls)).execute()
    assert [c[0] for c in calls] == ["a", "b"]
    assert calls[1][1] == {"path": "concepts/x.md", "fixo": 1}   # $prev
    assert result["state"] == "done"
    parsed = identity.parse(result["trace_id"])
    assert parsed["module"] == "pipeline"
    spans = [st["span"] for st in result["stages"]]
    assert len(set(spans)) == 2 and spans == sorted(spans)


def test_missing_prev_key_fails_the_stage_explicitly(settings):
    SavePipeline(settings, "furado", {"stages": [
        {"job": "b"},
        {"job": "c", "payload": {"x": "$prev.inexistente"}},
    ]}).execute()
    result = RunPipeline(settings, "furado", _registry([])).execute()
    assert result["state"] == "failed"
    assert "inexistente" in result["stages"][1]["error"]


def test_on_error_stop_vs_continue(settings):
    calls = []
    SavePipeline(settings, "para", {"stages": [
        {"job": "boom"}, {"job": "b"}]}).execute()
    stopped = RunPipeline(settings, "para", _registry(calls)).execute()
    assert stopped["state"] == "failed"
    assert [c[0] for c in calls] == ["boom"]      # b nunca rodou

    calls.clear()
    SavePipeline(settings, "segue", {"stages": [
        {"job": "boom", "on_error": "continue"}, {"job": "b"}]}).execute()
    partial = RunPipeline(settings, "segue", _registry(calls)).execute()
    assert partial["state"] == "partial"
    assert [c[0] for c in calls] == ["boom", "b"]
    states = [st["state"] for st in partial["stages"]]
    assert states == ["failed", "done"]


def test_runs_are_recorded_and_events_emitted(settings):
    events = []
    SavePipeline(settings, "gravado", {"stages": [{"job": "a"}]}).execute()
    RunPipeline(settings, "gravado", _registry([]),
                notify=lambda t, d: events.append((t, d))).execute()
    runs = pipeline_runs(settings, "gravado")
    assert runs[0]["state"] == "done"
    assert runs[0]["stages"][0]["job"] == "a"
    types = [t for t, _ in events]
    assert types.count("pipeline.stage") >= 2     # running + done
    assert types[-1] == "pipeline.done"
    assert all(d["trace_id"] for _, d in events)


# ------------------------------------------------------- ciclo de vida
def test_seed_save_and_delete(settings):
    seed_default_pipelines(settings)
    seed_default_pipelines(settings)              # idempotente
    names = {p["name"] for p in list_pipelines(settings)}
    assert set(DEFAULT_PIPELINES) <= names
    SavePipeline(settings, "meu-fluxo", {
        "description": "x", "stages": [{"job": "a"}]}).execute()
    SavePipeline(settings, "meu-fluxo", {
        "stages": [{"job": "b"}]}).execute()      # upsert
    mine = next(p for p in list_pipelines(settings)
                if p["name"] == "meu-fluxo")
    assert mine["stages"][0]["job"] == "b" and mine["builtin"] is False
    DeletePipeline(settings, "meu-fluxo").execute()
    with pytest.raises(KeyError):
        DeletePipeline(settings, "meu-fluxo").execute()


# --------------------------------------------------------------- HTTP
def test_http_contract_seeds_saves_runs(client):
    listed = client.get("/cockpit/pipelines").json()
    assert {p["name"] for p in listed["pipelines"]} >= set(DEFAULT_PIPELINES)
    assert listed["_links"]["run"]["href"] == "/cockpit/pipelines/run"

    bad = client.post("/cockpit/pipelines",
                      json={"name": "x!", "stages": [{"job": "a"}]})
    assert bad.status_code == 400

    ok = client.post("/cockpit/pipelines", json={
        "name": "so-indexar", "description": "reindex",
        "stages": [{"job": "index_rebuild"}]})
    assert ok.status_code == 200

    run = client.post("/cockpit/pipelines/run", json={"name": "so-indexar"})
    assert run.status_code == 200 and run.json()["job_id"]
    assert client.post("/cockpit/pipelines/run",
                       json={"name": "fantasma"}).status_code == 404

    assert client.delete("/cockpit/pipelines",
                         params={"name": "so-indexar"}).status_code == 200
    assert client.get("/cockpit/pipelines/runs").json()["runs"] == []


def test_pipeline_job_is_registered_and_heavy():
    from llmwiki.jobs import REGISTRY
    from llmwiki.runtime.slots import HEAVY
    assert "pipeline" in REGISTRY
    assert "pipeline" in HEAVY
    # os builtin só referenciam jobs que existem de verdade
    for spec in DEFAULT_PIPELINES.values():
        for stage in spec["stages"]:
            assert stage["job"] in REGISTRY, stage
