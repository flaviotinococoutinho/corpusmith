"""F0 (v1.8.1) — o doctor ganha porta HTTP (docs/15 §2, G-3).

`DiagnoseSystem` é o único verificador de INV-* do produto e vivia
alcançável só por `llmwiki doctor`: zero ocorrências de doctor/diagnose em
api/, facades/ e desktop/src. Sem porta, o app não pode mostrar índice
órfão nem oferecer reparo — e um invariante NOVO (o carimbo da camada de
padrões, F2-PR1) nasceria invisível na única superfície que a fase existe
para melhorar.
"""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.facades import SystemFacade
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue

TOKEN = "t0"


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    connect(settings.app_support / "index.db").close()
    from llmwiki.jobs import REGISTRY          # o daemon injeta; o teste imita
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token=TOKEN, known_jobs=set(REGISTRY))
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": TOKEN})
        yield c


def test_doctor_endpoint_exige_auth_e_devolve_invariantes(client):
    assert client.get("/system/doctor",
                      headers={"x-llmwiki-auth": "errado"}).status_code == 401
    r = client.get("/system/doctor")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"ok", "findings", "counts", "native"}
    assert set(body["counts"]) == {"error", "warn"}


def test_doctor_repara_indice_orfao_pela_api(client, settings, kb):
    """INV-001: chunk de página que não existe mais no bundle. O reparo
    era alcançável só por `llmwiki doctor --repair`."""
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/viva.md", body="# Viva\n\ncorpo.",
                     meta=OKFFrontMatter(type="concept", title="Viva",
                                         privacy="local_only",
                                         generated_via="human:promote"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT INTO chunks(page, ord, text) "
                "VALUES ('concepts/fantasma.md', 0, 'órfão')")
    idx.commit()
    idx.close()

    antes = client.get("/system/doctor").json()
    assert not antes["ok"] and antes["counts"]["error"] >= 1

    depois = client.post("/system/doctor/repair")
    assert depois.status_code == 200, depois.text
    corpo = depois.json()
    assert corpo["repaired"], "o reparo deveria ter rodado o rebuild"
    idx = connect(settings.app_support / "index.db")
    fantasma = idx.execute("SELECT COUNT(*) c FROM chunks WHERE "
                           "page='concepts/fantasma.md'").fetchone()["c"]
    idx.close()
    assert fantasma == 0, "o órfão deveria ter sido purgado pelo rebuild full"


def test_facade_sem_known_jobs_nao_derruba_a_checagem_de_pipeline(settings,
                                                                 kb):
    """Guarda de fiação: `DiagnoseSystem` desliga a checagem de pipelines
    em silêncio quando não recebe known_jobs (diagnose.py). A facade tem de
    repassar o conjunto que o daemon injeta — e sem ele ainda funcionar."""
    connect(settings.app_support / "index.db").close()
    assert SystemFacade(settings).doctor()["counts"]["error"] == 0
    from llmwiki.jobs import REGISTRY
    completo = SystemFacade(settings, set(REGISTRY)).doctor()
    assert completo["ok"] is True


def test_api_nao_importa_jobs_nem_a_facade(settings):
    """O `known_jobs` existe porque `jobs/` importa `facades/`: nem a
    camada HTTP nem a facade podem importar jobs de volta (ciclo + inversão
    do gradiente). Este teste crava a razão da injeção."""
    import llmwiki.api.system as api_system
    import llmwiki.facades.system as facade_system
    for module in (api_system, facade_system):
        fonte = __import__("inspect").getsource(module)
        assert "from ..jobs" not in fonte and "from .jobs" not in fonte, \
            f"{module.__name__} importa jobs — ciclo com facades"


# ==================== T10 residual: cancel/retry de jobs por HTTP
def test_cancel_e_retry_de_job_por_http(client, settings):
    """T10 (docs/18 §5.2): a fila tinha teste, a SUPERFÍCIE não — e é a
    superfície que o painel Processos chama (F-UI). Erro vira 409 com
    mensagem, nunca 500; shapes ficam presos aqui."""
    # enfileirar via HTTP e cancelar na hora (queued ⇒ cancelled)
    jid = client.post("/jobs", json={"type": "embed", "payload": {}}
                      ).json()["job_id"]
    r = client.post(f"/jobs/{jid}/cancel")
    assert r.status_code == 200
    assert r.json() == {"job_id": jid, "state": "cancelled"}
    # cancelado é reexecutável (retry_manual): volta a queued
    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 200
    assert r.json() == {"job_id": jid, "state": "queued"}
    # done não é cancelável ⇒ 409 nomeado, não 500
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("UPDATE jobs SET state='done' WHERE id=?", (jid,))
    rt.commit(); rt.close()
    assert client.post(f"/jobs/{jid}/cancel").status_code == 409
    assert client.post(f"/jobs/{jid}/retry").status_code == 409
    # job desconhecido ⇒ 409 (a fila não o conhece), não 500
    assert client.post("/jobs/nao-existe/cancel").status_code == 409
    assert client.post("/jobs/nao-existe/retry").status_code == 409
