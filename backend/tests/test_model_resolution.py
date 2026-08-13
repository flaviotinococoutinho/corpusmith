"""Resolução dinâmica do modelo local (ADR-42).

O modelo de chat deixa de ser um nome fixo e passa a ser uma ESCADA de
preferência resolvida contra a realidade da máquina: só entra o modelo
que está instalado E que cabe no orçamento de memória. Se nenhum cabe,
o roteador levanta `ModelUnavailable` — o contrato que os chamadores já
sabem degradar (extrativo/abstenção), nunca um `HTTPStatusError` cru.

Invariantes exercitados aqui: o roteador NÃO baixa modelo sozinho (uma
consulta jamais dispara download de GB) e falha de modelo NUNCA vira
exceção de transporte vazando para o caso de uso.
"""
from __future__ import annotations
import json
import httpx
import pytest
from corpusmith.models.router import ModelRouter, ModelUnavailable
from corpusmith.settings import Settings

GB = 1_000_000_000


def _settings(tmp_path, **local) -> Settings:
    base = {"provider": "ollama", "base_url": "http://127.0.0.1:11434",
            "chat": ["qwen3-vl:8b-instruct", "qwen3-vl:4b-instruct",
                     "qwen3-vl:4b", "qwen3-vl:2b-instruct"],
            "embed": "nomic-embed-text", "memory_fraction": 0.6}
    base.update(local)
    return Settings(home=tmp_path / "corpusmith", models={
        "local": base, "api": {"provider": "anthropic", "chat": "x"}})


def _stub_tags(monkeypatch, installed: dict[str, int]):
    """Finge o /api/tags do Ollama com {nome: bytes}."""
    payload = {"models": [{"name": n, "size": s} for n, s in installed.items()]}

    def fake_get(url, *a, **k):
        assert "/api/tags" in url
        return httpx.Response(200, json=payload,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr("corpusmith.models.router.httpx.get", fake_get)


def _stub_ram(monkeypatch, total_bytes: int):
    monkeypatch.setattr("corpusmith.models.router._total_ram_bytes",
                        lambda: total_bytes)


# --------------------------------------------------------------- resolução
def test_prefere_o_primeiro_da_escada_que_cabe(tmp_path, monkeypatch):
    """8b instalado numa máquina de 32 GB ⇒ ganha (é o topo da escada)."""
    _stub_ram(monkeypatch, 32 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:8b-instruct": int(6.14 * GB),
                             "qwen3-vl:4b": int(3.30 * GB)})
    assert ModelRouter(_settings(tmp_path)).resolve_chat() == \
        "qwen3-vl:8b-instruct"


def test_maquina_pequena_desce_para_o_modelo_menor(tmp_path, monkeypatch):
    """8 GB de RAM: 6.14 GB de pesos NÃO cabem em 0.6*8 = 4.8 GB ⇒ desce
    para o 4b, que está instalado e cabe. É o caso desta máquina."""
    _stub_ram(monkeypatch, 8 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:8b-instruct": int(6.14 * GB),
                             "qwen3-vl:4b": int(3.30 * GB)})
    assert ModelRouter(_settings(tmp_path)).resolve_chat() == "qwen3-vl:4b"


def test_pula_o_que_nao_esta_instalado(tmp_path, monkeypatch):
    """Preferido ausente não vira download: cai para o próximo presente."""
    _stub_ram(monkeypatch, 64 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:2b-instruct": int(1.89 * GB)})
    assert ModelRouter(_settings(tmp_path)).resolve_chat() == \
        "qwen3-vl:2b-instruct"


def test_nada_instalado_resolve_para_none(tmp_path, monkeypatch):
    _stub_ram(monkeypatch, 64 * GB)
    _stub_tags(monkeypatch, {})
    assert ModelRouter(_settings(tmp_path)).resolve_chat() is None


def test_nada_cabe_na_memoria_resolve_para_none(tmp_path, monkeypatch):
    """Modelo instalado porém maior que o orçamento: não é escolhido.
    Carregá-lo faria a máquina paginar até a inutilidade."""
    _stub_ram(monkeypatch, 4 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:8b-instruct": int(6.14 * GB)})
    assert ModelRouter(_settings(tmp_path)).resolve_chat() is None


def test_chat_como_string_continua_valendo(tmp_path, monkeypatch):
    """Compatibilidade: config antiga com um nome único segue funcionando."""
    _stub_ram(monkeypatch, 32 * GB)
    _stub_tags(monkeypatch, {"qwen2.5:7b-instruct": int(4.7 * GB)})
    r = ModelRouter(_settings(tmp_path, chat="qwen2.5:7b-instruct"))
    assert r.resolve_chat() == "qwen2.5:7b-instruct"


def test_tag_latest_casa_com_a_escada(tmp_path, monkeypatch):
    """Ollama devolve `nome:latest`; a escada pede `nome`. Devem casar."""
    _stub_ram(monkeypatch, 32 * GB)
    _stub_tags(monkeypatch, {"nomic-embed-text:latest": 274_000_000,
                             "qwen3-vl:4b-instruct:latest": int(3.3 * GB)})
    r = ModelRouter(_settings(tmp_path, chat=["qwen3-vl:4b-instruct"]))
    assert r.resolve_chat() == "qwen3-vl:4b-instruct:latest"


# ------------------------------------------------- falha soft, não de transporte
def test_ollama_no_ar_sem_modelo_levanta_model_unavailable(
        tmp_path, monkeypatch):
    """O bug encontrado na instalação: Ollama responde, o modelo pedido
    não existe (404) e o `HTTPStatusError` vazava até estourar o /ask.
    Agora tem de virar `ModelUnavailable` — contrato que degrada."""
    _stub_ram(monkeypatch, 32 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:4b": int(3.3 * GB)})

    def fake_post(url, *a, **k):
        return httpx.Response(
            404, json={"error": "model 'x' not found"},
            request=httpx.Request("POST", url))
    monkeypatch.setattr("corpusmith.models.router.httpx.post", fake_post)

    with pytest.raises(ModelUnavailable):
        ModelRouter(_settings(tmp_path)).complete("oi", privacy="local_only")


def test_ollama_offline_levanta_model_unavailable(tmp_path, monkeypatch):
    def boom(url, *a, **k):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr("corpusmith.models.router.httpx.get", boom)
    monkeypatch.setattr("corpusmith.models.router.httpx.post", boom)
    with pytest.raises(ModelUnavailable):
        ModelRouter(_settings(tmp_path)).complete("oi", privacy="local_only")


def test_resposta_vazia_nao_passa_por_sintese(tmp_path, monkeypatch):
    """Medido no qwen3-vl:4b (variante thinking): com num_predict curto o
    modelo gasta o orçamento no campo `thinking` e devolve `response`
    vazio com done_reason=length. Como `reconcile_candidate` pede 32
    tokens e `detect_communities` 160, isso é alcançável de verdade —
    e vazio não pode atravessar como se fosse resposta."""
    _stub_ram(monkeypatch, 32 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:4b": int(3.3 * GB)})

    def fake_post(url, *a, **k):
        return httpx.Response(
            200, json={"response": "", "thinking": "Okay, the user...",
                       "done_reason": "length"},
            request=httpx.Request("POST", url))
    monkeypatch.setattr("corpusmith.models.router.httpx.post", fake_post)

    with pytest.raises(ModelUnavailable, match="vazia"):
        ModelRouter(_settings(tmp_path)).complete(
            "oi", privacy="local_only", max_tokens=32)


def test_embed_falha_soft(tmp_path, monkeypatch):
    """embed também não vaza transporte: job falha com erro estável."""
    def fake_post(url, *a, **k):
        return httpx.Response(404, json={"error": "not found"},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr("corpusmith.models.router.httpx.post", fake_post)
    with pytest.raises(ModelUnavailable):
        ModelRouter(_settings(tmp_path)).embed(["texto"])


def test_resolucao_nao_dispara_download(tmp_path, monkeypatch):
    """Nenhum POST (logo, nenhum /api/pull) durante a resolução."""
    _stub_ram(monkeypatch, 8 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:4b": int(3.3 * GB)})

    def forbidden(*a, **k):
        raise AssertionError("resolução não pode fazer POST (nem pull)")
    monkeypatch.setattr("corpusmith.models.router.httpx.post", forbidden)
    assert ModelRouter(_settings(tmp_path)).resolve_chat() == "qwen3-vl:4b"


def test_via_reporta_o_modelo_efetivamente_usado(tmp_path, monkeypatch):
    """`via` é proveniência: precisa nomear o modelo RESOLVIDO, não o
    preferido que a máquina não conseguiu rodar."""
    _stub_ram(monkeypatch, 8 * GB)
    _stub_tags(monkeypatch, {"qwen3-vl:8b-instruct": int(6.14 * GB),
                             "qwen3-vl:4b": int(3.3 * GB)})

    seen: dict = {}

    def fake_post(url, *a, **k):
        seen.update(k.get("json") or {})
        return httpx.Response(200, json={"response": "ok"},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr("corpusmith.models.router.httpx.post", fake_post)

    out = ModelRouter(_settings(tmp_path)).complete("oi", privacy="local_only")
    assert seen["model"] == "qwen3-vl:4b"
    assert out["via"] == "local:qwen3-vl:4b"


def test_ask_degrada_para_extrativo_sem_modelo(settings, kb, monkeypatch):
    """Ponta a ponta: sem modelo utilizável, /ask responde extrativo em
    vez de estourar. É a promessa do docs/12 §6 valendo também no estado
    'Ollama de pé com modelo errado'."""
    from corpusmith.facades.memory import MemoryFacade
    from corpusmith.okf.document import OKFDocument, OKFFrontMatter
    from corpusmith.okf.writer import BundleWriter
    from corpusmith.retrieval.fts import rebuild_index

    monkeypatch.setattr(
        "corpusmith.models.router.ModelRouter.resolve_chat", lambda self: None)
    doc = OKFDocument(
        rel_path="pages/kubernetes.md",
        body="Kubernetes orquestra contêineres em cluster.",
        meta=OKFFrontMatter(title="Kubernetes", type="concept",
                            privacy="local_only",
                            generated_via="human:promote"))
    BundleWriter(kb).write([doc], log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)

    out = MemoryFacade(settings).ask("o que kubernetes orquestra?")
    assert out["via"] in ("local:extractive", "none")
    assert "Traceback" not in json.dumps(out)
