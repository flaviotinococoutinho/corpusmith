"""Q-33 — a busca densa compara vetores de UM espaço vetorial por vez.

`embeddings(chunk_id, model, vec)` grava o modelo de cada vetor, e nada o
lia:

- o job `embed` só embutia chunk SEM vetor (`WHERE e.chunk_id IS NULL`):
  trocar `models.local.embed` deixava os vetores antigos para sempre, e só
  os chunks novos recebiam o modelo novo;
- `dense.search` lia TODOS os vetores e embutia a pergunta com o modelo
  VIGENTE — cosseno entre espaços diferentes não é medida de nada;
- `_cos` usava `zip`, que trunca em silêncio vetores de dimensões
  diferentes. Medido: pergunta `[0, 0, 1, 5]` contra o vetor antigo
  `[0, 0, 1]` dava 0.196, e o chunk do modelo antigo ficava ACIMA do
  chunk do modelo correto, sem erro nenhum.

Só o rebuild completo (`DELETE FROM embeddings`) limpava a mistura. É a
classe da Q-28 (ADR-61) no instrumento semântico: a régua muda e a série
de medidas não registra quando.
"""
from __future__ import annotations

import json

import pytest

from corpusmith.harness.epistemics import load_registry
from corpusmith.jobs import embed as embed_job
from corpusmith.models.router import ModelRouter, ModelUnavailable
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval import dense
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect
from corpusmith.runtime.stages import StageProfile
from corpusmith.usecases.ask_memory import AskMemory

PERGUNTA = [0.0, 0.0, 1.0, 5.0]


class _Roteador:
    """Só o que a busca e o job usam do `ModelRouter`; registra o que
    embutiu (embutir à toa é chamada de modelo à toa)."""

    def __init__(self, vetor: list[float]):
        self.vetor = vetor
        self.embutidos: list[str] = []

    def local_available(self) -> bool:
        return True

    def embed(self, textos: list[str]) -> list[list[float]]:
        self.embutidos += textos
        return [list(self.vetor) for _ in textos]


def _com_modelo(settings, modelo: str):
    return settings.with_overrides(models={"local": {"embed": modelo}})


def _indice(s, linhas) -> None:
    """`linhas`: (chunk_id, modelo | None, vetor | None) — None = sem vetor."""
    idx = connect(s.app_support / "index.db")
    for cid, modelo, vetor in linhas:
        idx.execute("INSERT INTO chunks(id, page, ord, text) "
                    "VALUES (?,?,0,?)", (cid, f"concepts/c{cid}.md",
                                         f"texto {cid}"))
        if modelo is not None:
            idx.execute("INSERT INTO embeddings(chunk_id, model, vec) "
                        "VALUES (?,?,?)", (cid, modelo, json.dumps(vetor)))
    idx.commit()
    idx.close()


def _vetores(s) -> dict[int, tuple[str, list[float]]]:
    idx = connect(s.app_support / "index.db")
    try:
        return {r["chunk_id"]: (r["model"], json.loads(r["vec"]))
                for r in idx.execute(
                    "SELECT chunk_id, model, vec FROM embeddings")}
    finally:
        idx.close()


# ------------------------------------------------------- 1. a leitura
@pytest.mark.parametrize("vetor_antigo", [
    [0.0, 0.0, 1.0],            # o caso medido: zip truncava para 0.196
    [0.0, 0.0, 1.0, 5.0],       # mesma dimensão: só o NOME separa os espaços
], ids=["dimensao-diferente", "mesma-dimensao"])
def test_busca_densa_so_le_vetores_do_modelo_configurado(settings,
                                                         vetor_antigo):
    """Os dois casos reprovavam: o chunk do modelo antigo voltava ACIMA do
    chunk do modelo vigente. O de mesma dimensão é o que o guarda de
    dimensão nunca pegaria — prova que o filtro por modelo é o guarda
    PRIMÁRIO, e não um efeito colateral da checagem de dimensão."""
    s = _com_modelo(settings, "modelo-novo")
    _indice(s, [(1, "modelo-antigo", vetor_antigo),
                (2, "modelo-novo", [1.0, 0.0, 0.0, 0.0])])
    hits = dense.search(s, "pergunta", router=_Roteador(PERGUNTA))
    assert [h["id"] for h in hits] == [2]


def test_so_vetores_de_outro_modelo_deixa_o_stream_vazio(settings):
    """Enquanto o job não refaz nada, o stream denso fica VAZIO — cobertura
    parcial, nunca mistura — e a pergunta nem é embutida: sem vetor do
    espaço vigente não há com o que comparar."""
    s = _com_modelo(settings, "modelo-novo")
    _indice(s, [(1, "modelo-antigo", [0.0, 0.0, 1.0])])
    roteador = _Roteador(PERGUNTA)
    assert dense.search(s, "pergunta", router=roteador) == []
    assert roteador.embutidos == []


# ------------------------------------------------- 2. a convergência
def test_job_embed_refaz_o_vetor_de_outro_modelo(settings, monkeypatch):
    """Trocar `models.local.embed` converge sem rebuild: o vetor de outro
    modelo conta como AUSENTE e é refeito (`INSERT OR REPLACE`); o que já
    está no espaço vigente não é refeito; a segunda passada não tem o que
    fazer."""
    s = _com_modelo(settings, "modelo-novo")
    _indice(s, [(1, "modelo-antigo", [0.0, 0.0, 1.0]),
                (2, None, None),
                (3, "modelo-novo", [9.0, 9.0, 9.0, 9.0])])
    roteador = _Roteador(PERGUNTA)
    monkeypatch.setattr(embed_job, "ModelRouter", lambda _s: roteador)

    assert embed_job.run(s, {}, lambda *_: None)["embedded"] == 2
    assert sorted(roteador.embutidos) == ["texto 1", "texto 2"]
    assert _vetores(s) == {1: ("modelo-novo", PERGUNTA),
                           2: ("modelo-novo", PERGUNTA),
                           3: ("modelo-novo", [9.0, 9.0, 9.0, 9.0])}
    assert embed_job.run(s, {}, lambda *_: None)["embedded"] == 0


# ------------------------------------------------------ 3. a dimensão
def test_cosseno_recusa_dimensoes_divergentes():
    """`zip` truncava: `[0, 0, 1, 5]` × `[0, 0, 1]` virava 0.196. Cosseno
    entre dimensões diferentes não é medida — recusar é o único valor
    honesto."""
    with pytest.raises(ValueError, match="dimens"):
        dense._cos(PERGUNTA, [0.0, 0.0, 1.0])
    assert dense._cos(PERGUNTA, PERGUNTA) == pytest.approx(1.0)


def test_par_de_dimensao_divergente_sai_da_busca_e_fica_visivel(settings):
    """O filtro por NOME não separa um vetor de dimensão errada sob o nome
    vigente (re-pull do mesmo nome com outra dimensão, linha legada): o par
    é descartado — só ele, não o stream inteiro — e a contagem viaja no
    perfil da consulta em vez de sumir."""
    s = _com_modelo(settings, "modelo-novo")
    _indice(s, [(1, "modelo-novo", [0.0, 0.0, 1.0]),
                (2, "modelo-novo", [1.0, 0.0, 0.0, 0.0])])
    perfil = StageProfile("ask")
    hits = dense.search(s, "pergunta", router=_Roteador(PERGUNTA),
                        profile=perfil)
    assert [h["id"] for h in hits] == [2]
    assert perfil.data["ask.dense_dim_mismatch"] == 1


def test_o_ask_profundo_entrega_a_contagem_no_perfil(settings, kb,
                                                     monkeypatch):
    """A visibilidade é a do produto, não só a da função: o `/ask --deep`
    devolve o descarte no `profile` da resposta (o canal que já viaja no
    resultado, ADR-39)."""
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/vetor.md",
                     body="# Vetor\n\nUm texto qualquer sobre vetores.",
                     meta=OKFFrontMatter(type="concept", title="Vetor",
                                         privacy="local_only",
                                         generated_via="human:promote"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    modelo = settings.models["local"]["embed"]
    idx = connect(settings.app_support / "index.db")
    cid = idx.execute("SELECT id FROM chunks LIMIT 1").fetchone()["id"]
    idx.execute("INSERT INTO embeddings(chunk_id, model, vec) VALUES (?,?,?)",
                (cid, modelo, json.dumps([0.0, 0.0, 1.0])))
    idx.commit()
    idx.close()

    def _sem_modelo(*_a, **_k):
        raise ModelUnavailable("teste: composição extrativa")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(ModelRouter, "local_available", lambda self: True)
    monkeypatch.setattr(ModelRouter, "embed",
                        lambda self, textos: [list(PERGUNTA) for _ in textos])
    monkeypatch.setattr(ModelRouter, "complete", _sem_modelo)
    out = AskMemory(settings, "vetores", deep=True, local_only=True).execute()
    assert out["profile"]["ask.dense_dim_mismatch"] == 1


# ------------------------------------------------------ 4. o contrato
def test_o_contrato_da_fusao_declara_um_espaco_vetorial_por_vez():
    """A premissa mora no contrato do mecanismo que FUNDE os streams: RRF
    compara posições dentro de cada stream, e a posição no stream denso só
    significa algo se todos os scores dele vierem do mesmo espaço. O
    resíduo que o filtro por nome não pega fica declarado, não implícito."""
    registry, _ = load_registry()
    contrato = registry.get("retrieval_rrf_hedge")
    assert "backend/src/corpusmith/retrieval/dense.py" in \
        contrato.implementation_refs
    assert any("espaço vetorial" in a.text for a in contrato.assumptions)
    assert any("mesmo nome" in m.text
               for m in contrato.known_failure_modes)
