"""UX-5 (fatia métricas, P2 do backlog v1.3): as métricas fracionárias
do eval (recall@5/MRR médios, v1.6.3) ganham SUPERFÍCIE — o /cockpit/eval
e o /cockpit/quality expõem o que o Generalization Envelope já grava,
e o painel Qualidade mostra (anúncio sem UI era a dívida do UX-5)."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from corpusmith.api.system import build_app
from corpusmith.runtime.db import connect
from corpusmith.runtime.events import EventBus
from corpusmith.runtime.governor import Governor
from corpusmith.runtime.queue import JobQueue
from corpusmith.usecases.evaluate_memory import EvaluateMemory
from corpusmith.usecases.seed_eval import seed_golden_eval

TOKEN = "test-token"


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    connect(settings.app_support / "index.db").close()
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-corpusmith-auth": TOKEN})
        yield c


def test_cockpit_eval_expoe_metricas_fracionarias(settings, kb, client):
    seed_golden_eval(settings)
    EvaluateMemory(settings).execute()
    data = client.get("/cockpit/eval").json()
    assert data["categories"]                      # as 5 barras seguem lá
    metrics = data["metrics"]
    assert 0.0 < metrics["mean_recall_at_5"] <= 1.0
    assert 0.0 < metrics["mean_mrr"] <= 1.0
    assert metrics["overall_pass_rate"] == 1.0


def test_cockpit_quality_carrega_eval_metrics(settings, kb, client):
    seed_golden_eval(settings)
    EvaluateMemory(settings).execute()
    data = client.get("/cockpit/quality").json()
    assert data["eval_metrics"]["mean_mrr"] > 0.0


def test_sem_avaliacao_metricas_sao_nulas(client):
    data = client.get("/cockpit/eval").json()
    assert data["categories"] == [] and data["metrics"] is None
