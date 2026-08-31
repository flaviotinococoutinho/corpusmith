"""V4 — o índice "difícil de explicar" (RFC-006, docs/18 §10 item 5).

O que este pacote NÃO faz é metade do desenho, e está preso aqui:

- **não re-funde `low_yield`** com conflito. "ninguém achou útil" e "é
  difícil de explicar" são perguntas diferentes — o F4-PR2 gastou uma
  fase separando as duas, e somá-las de novo seria desfazer aquilo;
- **não confunde silêncio com facilidade**: página sem sinal nenhum sai
  com `medida=False`, não com "fácil". É a mesma disciplina do
  `measurable=false` da profundidade (v0.20);
- **não inventa precisão de nível**: o índice é por PÁGINA e fala de
  compreensão de afirmações — a granularidade está declarada no contrato
  em vez de fingida (docs/28 §2).
"""
from __future__ import annotations

import pytest

from corpusmith.kernel.difficulty import (COMPONENTES, PESOS, SATURACAO,
                                          consolidar, dificuldade)


# ------------------------------------------------------------ a composição
def test_sem_sinal_nao_e_facil_e_sim_nao_medida():
    d = dificuldade({})
    assert d.score == 0.0
    assert d.medida is False
    assert "sem sinal" in d.motivo


def test_um_sinal_ja_torna_a_pagina_medida():
    d = dificuldade({"conflito": 1})
    assert d.medida is True
    assert d.score > 0


def test_pesos_somam_um_e_cobrem_os_componentes():
    assert set(PESOS) == set(COMPONENTES) == set(SATURACAO)
    assert round(sum(PESOS.values()), 6) == 1.0


def test_todos_os_componentes_saturados_dao_um():
    d = dificuldade({c: SATURACAO[c] for c in COMPONENTES})
    assert d.score == 1.0


def test_componente_satura_e_nao_domina_sozinho():
    """Cem falhas confiantes não podem valer mais que o peso do
    componente — sem saturação, uma sessão de prática ruim afogaria
    todos os outros sinais."""
    muitas = dificuldade({"falha_confiante": 100})
    no_teto = dificuldade({"falha_confiante": SATURACAO["falha_confiante"]})
    assert muitas.score == no_teto.score == PESOS["falha_confiante"]


def test_low_yield_nao_entra_no_indice():
    """A armadilha nomeada pela RFC-006: `low_yield` é desfecho de uso,
    não dificuldade. Se um dia alguém o acrescentar como componente,
    este teste cai junto com o contrato."""
    assert "low_yield" not in COMPONENTES
    with pytest.raises(ValueError, match="componente"):
        dificuldade({"low_yield": 99})     # recusado, não somado em silêncio


def test_componente_desconhecido_e_recusado():
    """Silenciar chave desconhecida deixaria um componente novo entrar
    sem peso, sem contrato e sem ninguém notar."""
    with pytest.raises(ValueError, match="componente"):
        dificuldade({"inventado": 1})


def test_contagem_negativa_e_recusada():
    with pytest.raises(ValueError, match="negativ"):
        dificuldade({"conflito": -1})


def test_decomposicao_expoe_cada_parcela():
    d = dificuldade({"conflito": SATURACAO["conflito"], "pergunta_aberta": 0})
    assert d.componentes["conflito"] == PESOS["conflito"]
    assert d.componentes["pergunta_aberta"] == 0.0
    assert set(d.componentes) == set(COMPONENTES)


def test_motivo_nomeia_o_componente_dominante():
    d = dificuldade({"falha_confiante": SATURACAO["falha_confiante"],
                     "conflito": 1})
    assert "falha" in d.motivo.lower()


# ------------------------------------------------------------- o ranking
def test_consolidar_ordena_do_mais_dificil_para_o_menos():
    r = consolidar({"a.md": {"conflito": SATURACAO["conflito"]},
                    "b.md": {"pergunta_aberta": 1},
                    "c.md": {}})
    assert [e.rel_path for e in r] == ["a.md", "b.md", "c.md"]
    assert r[0].score > r[1].score > r[2].score == 0.0


def test_consolidar_desempata_por_caminho():
    """Determinismo: mesma entrada, mesma ordem — a projeção é comparável
    entre execuções (a mesma promessa do carimbo do mapa)."""
    r = consolidar({"z.md": {"conflito": 1}, "a.md": {"conflito": 1}})
    assert [e.rel_path for e in r] == ["a.md", "z.md"]


def test_consolidar_preserva_medida_por_pagina():
    r = {e.rel_path: e for e in consolidar({"a.md": {"conflito": 1},
                                            "b.md": {}})}
    assert r["a.md"].medida is True
    assert r["b.md"].medida is False


def test_consolidar_e_puro_nao_muta_a_entrada():
    entrada = {"a.md": {"conflito": 1}}
    consolidar(entrada)
    assert entrada == {"a.md": {"conflito": 1}}


# ================================================= a coleta (use case real)
#
# Cada teste abaixo exercita UM dono de sinal pelo caminho de produção — a
# lição da 3ª rodada de QA: teste que monta a estrutura à mão prova que o
# kernel soma, não que o produto colhe.
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.usecases.compute_difficulty import ComputeDifficulty
from corpusmith.usecases.ask_memory import AskMemory


def _doc(rel, title, body, **meta):
    meta.setdefault("type", "concept")
    meta.setdefault("privacy", "local_only")
    meta.setdefault("generated_via", "human:promote")
    return OKFDocument(rel_path=rel, body=body,
                       meta=OKFFrontMatter(title=title, **meta))


def _write(settings, kb, *docs):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message="c")
    rebuild_index(settings)


def _por_pagina(resultado):
    return {e["rel_path"]: e for e in resultado["difficulty"]}


def test_pergunta_aberta_conta_para_a_pagina_apontada(settings, kb):
    _write(settings, kb,
           _doc("concepts/alvo.md", "Alvo", "# Alvo\n\nConteúdo."),
           _doc("questions/q1.md", "Como isso funciona?",
                "# Como isso funciona?\n\nVer [Alvo](../concepts/alvo.md).",
                type="question"))
    r = _por_pagina(ComputeDifficulty(settings).execute())
    assert r["concepts/alvo.md"]["componentes"]["pergunta_aberta"] > 0
    assert r["concepts/alvo.md"]["medida"] is True


def test_pergunta_respondida_para_de_contar(settings, kb):
    """`answered_by` é o gesto humano que fecha — e fechar tem de tirar a
    página da lista, ou a fila volta a propor o que já foi resolvido."""
    _write(settings, kb,
           _doc("concepts/alvo.md", "Alvo", "# Alvo\n\nConteúdo."),
           _doc("questions/q1.md", "Como isso funciona?",
                "# Como isso funciona?\n\nVer [Alvo](../concepts/alvo.md).",
                type="question", answered_by="concepts/alvo.md"))
    r = _por_pagina(ComputeDifficulty(settings).execute())
    assert r["concepts/alvo.md"]["componentes"]["pergunta_aberta"] == 0
    assert r["concepts/alvo.md"]["medida"] is False


def test_conflito_conta_para_TODAS_as_paginas_do_grupo(settings, kb):
    """O finding aponta a mais entrincheirada, mas quem lê qualquer uma
    das duas tromba no mesmo desacordo — atribuir só ao alvo deixaria a
    outra metade do conflito invisível no índice."""
    _write(settings, kb,
           _doc("concepts/a.md", "A",
                "# A\n\nO artigo DOI 10.1000/xyz mede 10 km."),
           _doc("concepts/b.md", "B",
                "# B\n\nO artigo DOI 10.1000/xyz mede 40 km."))
    r = _por_pagina(ComputeDifficulty(settings).execute())
    assert r["concepts/a.md"]["componentes"]["conflito"] > 0
    assert r["concepts/b.md"]["componentes"]["conflito"] > 0


def test_falha_confiante_da_pratica_entra_no_indice(settings, kb):
    _write(settings, kb, _doc("concepts/dificil.md", "Difícil",
                              "# Difícil\n\nAssunto espinhoso."))
    cog = connect(settings.app_support / "cognitive.db")
    cog.execute("INSERT INTO retrieval_attempts(session_id, item, exercise,"
                " confidence_before, result) VALUES(?,?,?,?,?)",
                ("s1", "concepts/dificil.md", "recall", 0.95, "failure"))
    cog.commit(); cog.close()
    r = _por_pagina(ComputeDifficulty(settings).execute())
    assert r["concepts/dificil.md"]["componentes"]["falha_confiante"] > 0
    assert "falha" in r["concepts/dificil.md"]["motivo"].lower()


def test_falha_SEM_confianca_nao_conta_como_dificuldade(settings, kb):
    """Errar sabendo que não sabia é ignorância honesta — o sinal caro é
    a sobreconfiança (mesmo limiar do spaced-v1)."""
    _write(settings, kb, _doc("concepts/p.md", "P", "# P\n\nTexto."))
    cog = connect(settings.app_support / "cognitive.db")
    cog.execute("INSERT INTO retrieval_attempts(session_id, item, exercise,"
                " confidence_before, result) VALUES(?,?,?,?,?)",
                ("s1", "concepts/p.md", "recall", 0.1, "failure"))
    cog.commit(); cog.close()
    r = _por_pagina(ComputeDifficulty(settings).execute())
    assert r["concepts/p.md"]["componentes"]["falha_confiante"] == 0


def test_lacuna_recorrente_do_F6_alcanca_a_pagina_do_assunto(settings, kb):
    """O elo F6 → V4: a base se absteve sobre PostgreSQL, e a página que
    fala de PostgreSQL herda o sinal (salto de nível declarado)."""
    faltou = AskMemory(settings, "PostgreSQL", local_only=True).execute()
    assert faltou["abstained"] is True          # o buraco existe primeiro…
    _write(settings, kb,                        # …e a página chega depois
           _doc("concepts/pg.md", "PostgreSQL",
                "# PostgreSQL\n\nNotas sobre PostgreSQL."))
    r = _por_pagina(ComputeDifficulty(settings).execute())
    assert r["concepts/pg.md"]["componentes"]["lacuna_recorrente"] > 0


def test_miss_fechado_nao_alimenta_o_indice(settings, kb):
    """Fechado por re-ask é buraco PROVADO fechado — ressuscitá-lo aqui
    contradiria o F6 e faria a dificuldade crescer com o tempo mesmo em
    base que melhorou."""
    AskMemory(settings, "postgresql", local_only=True).execute()
    _write(settings, kb,
           _doc("concepts/pg.md", "PostgreSQL",
                "# PostgreSQL\n\nNotas sobre PostgreSQL."))
    AskMemory(settings, "postgresql", local_only=True).execute()   # fecha
    r = _por_pagina(ComputeDifficulty(settings).execute())
    assert r["concepts/pg.md"]["componentes"]["lacuna_recorrente"] == 0


def test_projecao_persiste_e_e_substituida_por_completo(settings, kb):
    _write(settings, kb, _doc("concepts/a.md", "A", "# A\n\nTexto."))
    ComputeDifficulty(settings).execute()
    ComputeDifficulty(settings).execute()          # idempotente
    idx = connect(settings.app_support / "index.db")
    linhas = [dict(r) for r in idx.execute("SELECT * FROM page_difficulty")]
    idx.close()
    assert len(linhas) == 1
    assert linhas[0]["rel_path"] == "concepts/a.md"
    assert linhas[0]["measured"] == 0                # sem sinal ≠ fácil


def test_dificuldade_nao_declara_derivacao_na_cadeia():
    """Decisão DELIBERADA, presa por teste: dois dos cinco sinais são de
    USO (prática, abstenção) e não movem o HEAD do bundle. Declarar
    `difficulty` em DERIVATIONS prometeria um frescor que a cadeia não
    entrega — o doctor diria "fresca" com a prática de ontem."""
    from corpusmith.kernel.checkpoints import DERIVATIONS
    assert "difficulty" not in DERIVATIONS


def test_limiar_de_sobreconfianca_e_o_mesmo_do_spaced_v1():
    """Uma definição de "confiante" no produto, não duas.

    A memória não importa `cognitive/` (asserção de arquitetura), então a
    constante é repetida — e repetir constante só é honesto se algo
    quebrar quando as duas divergirem. É este teste. Falsificável: mude
    `_CONFIANCA` (ou o default do spaced-v1) e ele reprova."""
    from corpusmith.cognitive.policy import validate_policy
    from corpusmith.usecases.compute_difficulty import _CONFIANCA
    assert _CONFIANCA == validate_policy({})["review"][
        "overconfidence_threshold"]


def test_a_memoria_nao_importa_o_dominio_cognitivo():
    """V4 é cross-domain por natureza — e é exatamente por isso que a
    fronteira precisa de guarda. `cognitive.db` é lido como DADO (uma
    projeção de prática); o MÓDULO `cognitive/` continua fora do alcance
    da memória, que é o que a asserção de arquitetura promete."""
    import ast
    from pathlib import Path
    from corpusmith.usecases import compute_difficulty
    src = Path(compute_difficulty.__file__).read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            assert "cognitive" not in (node.module or "")
        elif isinstance(node, ast.Import):
            assert all("cognitive" not in a.name for a in node.names)
