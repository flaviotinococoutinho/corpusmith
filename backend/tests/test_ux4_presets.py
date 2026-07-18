"""UX-4 (P1 do backlog v1.3): presets de configuração — conjuntos
NOMEADOS de ajustes que passam pela MESMA linhagem do TuneConfig
(source=preset:<nome>, guard de fitness, ring de 30, rollback O(1)).
Aplicar um preset é uma geração; desfazer é o rollback de sempre."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.facades.curation import CurationFacade
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue
from llmwiki.settings import Settings
from llmwiki.usecases.configure_system import (PRESETS, config_history,
                                               list_presets)

TOKEN = "test-token"


# ------------------------------------------------------------ dados/contrato
def test_ha_pelo_menos_3_presets_com_descricao():
    assert len(PRESETS) >= 3
    for name, preset in PRESETS.items():
        assert preset["description"]
        assert preset["changes"], name


def test_presets_so_tocam_secoes_ajustaveis():
    for name, preset in PRESETS.items():
        for section in preset["changes"]:
            assert section in Settings.TUNABLE_SECTIONS, f"{name}.{section}"


def test_todo_preset_aplica_num_settings_virgem(settings):
    """Nenhum preset pode conter chave/tipo que o guard rejeite."""
    for name in PRESETS:
        CurationFacade(settings).apply_preset(name)


# ------------------------------------------------------- linhagem e rollback
def test_aplicar_preset_registra_na_linhagem_com_source(settings):
    out = CurationFacade(settings).apply_preset("precisao")
    assert out["history_id"]
    top = config_history(settings, 1)[0]
    assert top["source"] == "preset:precisao"
    assert settings.get("consolidate.min_shared") == 3     # aplicado a quente


def test_rollback_desfaz_preset(settings):
    facade = CurationFacade(settings)
    facade.apply_preset("precisao")
    assert settings.get("consolidate.min_shared") == 3
    facade.rollback_config()
    assert settings.get("consolidate.min_shared") == 2     # de volta


def test_preset_desconhecido_levanta_keyerror(settings):
    with pytest.raises(KeyError):
        CurationFacade(settings).apply_preset("nao-existe")


# --------------------------------------------------------------------- API
@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    connect(settings.app_support / "index.db").close()
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": TOKEN})
        yield c


def test_get_presets_lista_com_hateoas(client):
    r = client.get("/cockpit/config/presets")
    assert r.status_code == 200
    data = r.json()
    names = {p["name"] for p in data["presets"]}
    assert {"fabrica", "precisao", "exploracao"} <= names
    assert "_links" in data


def test_post_preset_aplica_e_devolve_linhagem(client):
    r = client.post("/cockpit/config/preset", json={"name": "exploracao"})
    assert r.status_code == 200
    data = r.json()
    assert data["history_id"] and data["memory"]["auto_recycle"] is True


def test_post_preset_desconhecido_e_404(client):
    assert client.post("/cockpit/config/preset",
                       json={"name": "zzz"}).status_code == 404


def test_post_preset_sem_name_e_422(client):
    assert client.post("/cockpit/config/preset", json={}).status_code == 422
