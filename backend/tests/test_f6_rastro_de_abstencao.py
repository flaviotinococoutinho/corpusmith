"""F6 — rastro de abstenção (P-8, RFC-006): a memória lembra o que falhou.

Antes: a abstenção retornava sem tocar o runtime.db — a ignorância mais
cara (a que o usuário realmente tentou usar) não deixava rastro, e a
recorrência era invisível. Agora: todo `/ask` abstido grava um miss em
`ask_misses` com chave DETERMINÍSTICA (conjunto de entidades da pergunta;
sem entidade curada, SimHash do texto normalizado — precisão > recall,
declarado no contrato `abstention_trace`), e o fechamento é VERIFICADO
POR RE-ASK: só uma consulta com a MESMA chave que responde fecha o
rastro — nenhum job adivinha cobertura. É o sinal que V4 (índice
"difícil de explicar") vai consumir.
"""
from __future__ import annotations
import json

from corpusmith.kernel.sketch import miss_key
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.retrieval.observatory import insights
from corpusmith.runtime.db import connect
from corpusmith.usecases.ask_memory import AskMemory


def _write(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _misses(settings):
    rt = connect(settings.app_support / "runtime.db")
    rows = [dict(r) for r in rt.execute(
        "SELECT * FROM ask_misses ORDER BY id")]
    rt.close()
    return rows


# ------------------------------------------------------- a chave (pura)
def test_miss_key_junta_frases_diferentes_sobre_as_mesmas_entidades():
    """Perguntas sobre o MESMO conjunto de sujeitos são o mesmo buraco."""
    a = miss_key("o que é a ISO 27001?", {"ISO 27001"})
    b = miss_key("explique a ISO 27001 em detalhes", {"ISO 27001"})
    c = miss_key("o que é a ISO 9001?", {"ISO 9001"})
    assert a == b
    assert a != c
    assert a.startswith("e:")


def test_miss_key_sem_entidades_cai_para_o_texto_normalizado():
    """Sem entidade curada só quase-idênticas recorrem — recall limitado
    e DECLARADO (contrato `abstention_trace`), nunca chave instável."""
    a = miss_key("história do egito antigo", set())
    b = miss_key("  História   do Egito ANTIGO ", set())
    c = miss_key("dinastias da mesopotâmia", set())
    assert a == b
    assert a != c
    assert a.startswith("s:")


def test_miss_key_ignora_entidade_vazia_e_ordem():
    assert miss_key("x", {"B", "a"}) == miss_key("y", {"A ", "b", ""})


# ------------------------------------------------- gravação na abstenção
def test_abstencao_grava_o_miss(settings, kb):
    r = AskMemory(settings, "história do egito antigo",
                  local_only=True).execute()
    assert r["abstained"] is True
    rows = _misses(settings)
    assert len(rows) == 1
    assert rows[0]["ask_id"] == r["ask_id"]
    assert rows[0]["miss_key"] == miss_key("história do egito antigo", set())
    assert rows[0]["closed_at"] is None
    assert json.loads(rows[0]["gaps"])          # lacunas nomeadas viajam


def test_sucesso_nao_grava_miss(settings, kb):
    _write(settings, kb,
           _doc("concepts/golfinhos.md", "Golfinhos",
                "# Golfinhos\n\nEcolocalização em golfinhos."))
    r = AskMemory(settings, "golfinhos", local_only=True).execute()
    assert r["abstained"] is False
    assert _misses(settings) == []


# ------------------------------------------- fechamento verificado por re-ask
def test_sucesso_fecha_o_miss_da_mesma_pergunta(settings, kb):
    r1 = AskMemory(settings, "golfinhos", local_only=True).execute()
    assert r1["abstained"] is True
    _write(settings, kb,
           _doc("concepts/golfinhos.md", "Golfinhos",
                "# Golfinhos\n\nEcolocalização em golfinhos."))
    r2 = AskMemory(settings, "golfinhos", local_only=True).execute()
    assert r2["abstained"] is False
    (row,) = _misses(settings)
    assert row["closed_at"] is not None
    assert row["closed_by"] == r2["ask_id"]     # o re-ask que PROVOU


def test_pergunta_diferente_nao_fecha_o_miss(settings, kb):
    AskMemory(settings, "história do egito antigo",
              local_only=True).execute()
    _write(settings, kb,
           _doc("concepts/golfinhos.md", "Golfinhos",
                "# Golfinhos\n\nEcolocalização em golfinhos."))
    r = AskMemory(settings, "golfinhos", local_only=True).execute()
    assert r["abstained"] is False
    aberto = [m for m in _misses(settings) if m["closed_at"] is None]
    assert len(aberto) == 1                     # o buraco do Egito segue lá


def test_fechamento_preserva_o_primeiro_fechador(settings, kb):
    AskMemory(settings, "golfinhos", local_only=True).execute()
    _write(settings, kb,
           _doc("concepts/golfinhos.md", "Golfinhos",
                "# Golfinhos\n\nEcolocalização em golfinhos."))
    r2 = AskMemory(settings, "golfinhos", local_only=True).execute()
    r3 = AskMemory(settings, "golfinhos", local_only=True).execute()
    assert r3["abstained"] is False
    (row,) = _misses(settings)
    assert row["closed_by"] == r2["ask_id"]     # auditoria: quem fechou, fechou


def test_re_ask_com_outra_frase_fecha_pelo_conjunto_de_entidades(
        settings, kb):
    """O payoff da chave por entidades: "PostgreSQL em produção" e "como
    usar postgres?" são o MESMO buraco (canônico via gazetteer), mesmo
    com SimHash completamente diferente."""
    r1 = AskMemory(settings, "PostgreSQL em produção",
                   local_only=True).execute()
    assert r1["abstained"] is True
    (row,) = _misses(settings)
    assert row["miss_key"].startswith("e:")
    _write(settings, kb,
           _doc("concepts/pg.md", "PostgreSQL",
                "# PostgreSQL\n\nOperação de PostgreSQL em produção."))
    r2 = AskMemory(settings, "como usar postgres?",
                   local_only=True).execute()
    assert r2["abstained"] is False
    (row,) = _misses(settings)
    assert row["closed_by"] == r2["ask_id"]


# ------------------------------------------------------------- superfície
def test_insights_expoe_a_abstencao_com_recorrencia(settings, kb):
    AskMemory(settings, "história do egito antigo",
              local_only=True).execute()
    AskMemory(settings, "história do egito antigo",
              local_only=True).execute()
    bloco = insights(settings)["gaps"]["abstention"]
    assert bloco["open"] == 2
    assert bloco["recurrent"][0]["n"] == 2
    assert "egito" in bloco["recurrent"][0]["query"]
