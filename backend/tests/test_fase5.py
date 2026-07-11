"""Fase 5 (v0.15): observatório (grafo/insights/dicionário/tracing),
gerenciador de tags, config viva, comportamento da IA e exporter."""
from __future__ import annotations
import io
import json
import zipfile
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.facades import CurationFacade, MemoryFacade
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue
from llmwiki.settings import Settings


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
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _seed(settings, kb):
    docs = [
        _doc("concepts/grpc.md", "gRPC", "# gRPC\n\ngRPC no backbone; ver "
             "[mensageria](/concepts/mensageria.md).", tags=["infra", "rede"]),
        _doc("concepts/mensageria.md", "Mensageria",
             "# Mensageria\n\nRabbitMQ conecta tudo.", tags=["infra"]),
        _doc("questions/latencia.md", "Latência aberta",
             "# Latência\n\npendente medir.", type="question",
             privacy="api_allowed"),
    ]
    BundleWriter(kb).write(docs, log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


# ------------------------------------------------------------ observatório
def test_graph_insights_dictionary_shapes(client, settings, kb):
    _seed(settings, kb)
    g = client.get("/cockpit/graph").json()
    nodes = {n["page"]: n for n in g["nodes"]}
    assert nodes["concepts/mensageria.md"]["orphan"] is False
    assert nodes["questions/latencia.md"]["orphan"] is True
    assert any(e["src"] == "concepts/grpc.md" for e in g["edges"])
    assert {"degree", "heat", "community", "type"} <= set(
        nodes["concepts/grpc.md"])

    ins = client.get("/cockpit/insights").json()
    assert set(ins) == {"gaps", "topology", "activity", "classifiers"}
    assert "questions/latencia.md" in ins["gaps"]["questions"]
    assert ins["topology"]["nodes"] == 3
    assert ins["classifiers"]["by_privacy"]

    d = client.get("/cockpit/dictionary").json()
    assert {"types", "origins", "confidence_scale", "verdicts",
            "authorities", "gazetteer_terms"} <= set(d)
    assert any(t["type"] == "question" and t["uses"] == 1 for t in d["types"])


def test_traces_after_ask_and_outcome(client, settings, kb):
    _seed(settings, kb)
    r = MemoryFacade(settings).ask("gRPC no backbone", local_only=True)
    MemoryFacade(settings).record_outcome(
        verdict="useful", ask_id=r["ask_id"],
        pages=[e["page"] for e in r["evidence"]])
    traces = client.get("/cockpit/traces").json()["traces"]
    assert traces[0]["ask_id"] == r["ask_id"]
    assert traces[0]["verdict"] == "useful"
    detail = client.get("/cockpit/trace",
                        params={"ask_id": r["ask_id"]}).json()
    assert any(p["page"] == "concepts/grpc.md" for p in detail["pages"])
    assert detail["outcome"]["verdict"] == "useful"
    assert detail["stream_weights"]              # Hedge já registrou


# ------------------------------------------------------- gerenciador de tags
def test_tag_rename_merge_and_remove(client, settings, kb):
    _seed(settings, kb)
    tags = dict(client.get("/cockpit/tags").json()["tags"])
    assert tags == {"infra": 2, "rede": 1}
    # renomear rede → redes
    r = client.post("/cockpit/tags", json={"from": "rede", "to": "redes"})
    assert r.json()["pages"] == 1
    # fundir redes em infra (não duplica)
    client.post("/cockpit/tags", json={"from": "redes", "to": "infra"})
    tags = dict(client.get("/cockpit/tags").json()["tags"])
    assert tags == {"infra": 2}
    # remover
    client.post("/cockpit/tags", json={"from": "infra"})
    assert client.get("/cockpit/tags").json()["tags"] == []
    assert client.post("/cockpit/tags", json={"to": "x"}).status_code == 400


# --------------------------------------------------------- config viva
def test_config_tunes_live_and_persists(client, settings, kb):
    _seed(settings, kb)
    snap = client.get("/cockpit/config").json()
    assert set(snap) == set(Settings.TUNABLE_SECTIONS)
    # sobe o threshold de abstenção a quente → o ask passa a abster
    r = client.post("/cockpit/config",
                    json={"ask": {"abstain_threshold": 99.0}})
    assert r.json()["ask"]["abstain_threshold"] == 99.0
    assert MemoryFacade(settings).ask("gRPC", local_only=True)["abstained"]
    client.post("/cockpit/config", json={"ask": {"abstain_threshold": 0.0}})
    assert not MemoryFacade(settings).ask("gRPC", local_only=True)["abstained"]
    # persistência: um novo load() enxerga o override
    import os
    os.environ["LLMWIKI_HOME"] = str(settings.home)
    try:
        client.post("/cockpit/config", json={"memory": {"min_idle_days": 33}})
        reloaded = Settings.load()
        assert reloaded.get("memory.min_idle_days") == 33
    finally:
        del os.environ["LLMWIKI_HOME"]
    # seção desconhecida → 400
    assert client.post("/cockpit/config",
                       json={"server": {"port": 1}}).status_code == 400


def test_behavior_and_stream_reset(client, settings, kb):
    _seed(settings, kb)
    r = MemoryFacade(settings).ask("gRPC no backbone", local_only=True)
    MemoryFacade(settings).record_outcome(
        verdict="dead_end", ask_id=r["ask_id"],
        pages=[e["page"] for e in r["evidence"]])
    b = client.get("/cockpit/behavior").json()
    assert b["stream_weights"] and all(w < 1.0
                                       for w in b["stream_weights"].values())
    assert "flags" in b and "eval" in b
    client.post("/cockpit/behavior/reset-streams")
    assert client.get("/cockpit/behavior").json()["stream_weights"] == {}


# ------------------------------------------------------------- exporter
def test_export_respects_privacy_and_formats(client, settings, kb):
    _seed(settings, kb)      # 2 local_only + 1 api_allowed
    # default: só a pública sai
    r = client.get("/cockpit/export", params={"format": "json"})
    payload = json.loads(r.content)
    assert payload["manifest"]["pages"] == 1
    assert payload["manifest"]["excluded_local_only"] == 2
    assert payload["pages"][0]["path"] == "questions/latencia.md"
    # include_local=true traz tudo; zip carrega manifest + arquivos
    r = client.get("/cockpit/export",
                   params={"format": "zip", "include_local": "true"})
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert "manifest.json" in names
    assert "bundle/concepts/grpc.md" in names
    assert json.loads(zf.read("manifest.json"))["pages"] == 3
    # md digest com filtro por tag
    r = client.get("/cockpit/export",
                   params={"format": "md", "include_local": "true",
                           "tag": "rede"})
    assert b"gRPC" in r.content and b"Mensageria" not in r.content
    assert "attachment" in r.headers["content-disposition"]
    # formato inválido → 400
    assert client.get("/cockpit/export",
                      params={"format": "docx"}).status_code == 400


def test_export_via_facade_filters_types(settings, kb):
    _seed(settings, kb)
    result = CurationFacade(settings).export(
        format="json", include_local=True, types=["question"])
    payload = json.loads(result["content"])
    assert [p["path"] for p in payload["pages"]] == ["questions/latencia.md"]
