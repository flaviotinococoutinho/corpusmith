"""Borda HTTP tipada: corpo malformado em /ask e /jobs responde 422,
nunca 500 (AGENTS §5 — `dict[str, Any]` cru não atravessa camadas; o
KeyError na borda virava Internal Server Error sem código estável)."""
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


def test_ask_sem_query_responde_422(client):
    r = client.post("/ask", json={"question": "campo errado"})
    assert r.status_code == 422


def test_ask_query_nao_string_responde_422(client):
    r = client.post("/ask", json={"query": ["lista", "não", "vale"]})
    assert r.status_code == 422


def test_jobs_sem_type_responde_422(client):
    r = client.post("/jobs", json={"payload": {}})
    assert r.status_code == 422


def test_ask_valido_segue_abstendo_sem_cobertura(client):
    r = client.post("/ask", json={"query": "pergunta sem cobertura alguma"})
    assert r.status_code == 200
    assert r.json()["abstained"] is True


def test_jobs_valido_enfileira(client):
    r = client.post("/jobs", json={"type": "reindex", "payload": {}})
    assert r.status_code == 200
    assert r.json()["job_id"]
