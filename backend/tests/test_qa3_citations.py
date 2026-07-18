"""QA-3 (P1 do backlog v1.3): validação ESTRUTURAL [n]→evidência no /ask.

Resposta sintetizada (local: OU api:) que cita [n] sem correspondência na
evidência é fabricação de proveniência — degrada para o modo extrativo
(correto por construção; `via` sinaliza a degradação). Precisão > recall:
só o que é claramente citação ([n] de 1–2 dígitos fora de link markdown)
é validado — [2024] é ano, não citação."""
from __future__ import annotations
import pytest
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.usecases.ask_memory import AskMemory, _invalid_citations


# ------------------------------------------------------------- helper puro
def test_citacao_dentro_da_evidencia_e_valida():
    assert _invalid_citations("Conforme [1] e [2].", 2) == []


def test_citacao_fora_da_evidencia_e_flagrada():
    assert _invalid_citations("Conforme [3].", 2) == [3]
    assert _invalid_citations("Zero é inválido [0].", 2) == [0]


def test_ano_e_link_markdown_nao_sao_citacao():
    assert _invalid_citations("Em [2024] houve.", 1) == []          # 4 dígitos
    assert _invalid_citations("ver [1](https://x) e [9](y)", 1) == []  # link


def test_sem_evidencia_qualquer_citacao_e_invalida():
    assert _invalid_citations("Conforme [1].", 0) == [1]


# ------------------------------------------------------- fim-a-fim no /ask
def _indexed_page(settings, kb):
    doc = OKFDocument(
        rel_path="concepts/kubernetes.md",
        body="# Kubernetes\n\nKubernetes orquestra containers em cluster "
             "com scheduler e kubelet.",
        meta=OKFFrontMatter(type="concept", title="Kubernetes",
                            privacy="local_only"))
    BundleWriter(kb).write([doc], log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)


def _fake_complete(text):
    def fake(self, prompt, **kwargs):
        return {"text": text, "via": "local:fake", "usd": 0.0}
    return fake


def test_sintese_com_citacao_fabricada_degrada_para_extrativo(
        settings, kb, monkeypatch):
    _indexed_page(settings, kb)
    monkeypatch.setattr(
        "llmwiki.models.router.ModelRouter.complete",
        _fake_complete("Kubernetes faz X [7].\n\n# Citations\n[7] inventada.md"))
    out = AskMemory(settings, "kubernetes scheduler").execute()
    assert out["abstained"] is False and out["evidence"]
    assert out["via"] == "local:extractive"        # degradou: [7] não existe
    assert out["blocked"] is False
    assert "[1]" in out["answer"]                  # extrativo cita o real


def test_sintese_com_citacao_valida_passa_intacta(settings, kb, monkeypatch):
    _indexed_page(settings, kb)
    monkeypatch.setattr(
        "llmwiki.models.router.ModelRouter.complete",
        _fake_complete("Kubernetes orquestra [1].\n\n# Citations\n"
                       "[1] concepts/kubernetes.md"))
    out = AskMemory(settings, "kubernetes scheduler").execute()
    assert out["abstained"] is False
    assert out["via"] == "local:fake"              # síntese aceita
    assert "orquestra [1]" in out["answer"]
