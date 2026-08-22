"""RFC-006 V3 — estabilidade editorial: o que menos muda.

O primeiro pacote da fila reordenada (`docs/18` §10): projeção pura de
bundle+Git, sem LLM, sem limiar. A armadilha nomeada pela RFC-006 §3 é o
score único somando sentidos diferentes de "mudança" — por isso os testes
daqui prendem a SEPARAÇÃO (edição ≠ ciclo ≠ uso ≠ tema) tanto quanto o
cálculo.
"""
from __future__ import annotations
import pytest
from corpusmith.kernel.checkpoints import DERIVATIONS
from corpusmith.kernel.stability import (BASENAMES_REGENERADOS,
                                         PREFIXOS_DE_RITUAL, Estabilidade,
                                         conta_para_estabilidade, consolidar)
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.git_store import GitStore
from corpusmith.okf.writer import BundleWriter
from corpusmith.runtime.checkpoints import verify
from corpusmith.runtime.db import connect
from corpusmith.usecases.compute_stability import ComputeStability


def _doc(rel, title, **meta):
    return OKFDocument(rel_path=rel, body=f"# {title}\n\nprosa.",
                       meta=OKFFrontMatter(type="concept", title=title,
                                           privacy="local_only", **meta))


def _escreve(kb, *docs, msg="c"):
    BundleWriter(kb).write(list(docs), log_kind="Creation",
                           log_message="m", commit_message=msg)


def _edita(kb, *docs, msg="c"):
    BundleWriter(kb).write(list(docs), log_kind="Update",
                           log_message="m", commit_message=msg)


# ================================================ a regra pura (kernel)
def test_regenerados_e_ritual_ficam_fora_da_medicao():
    """`writer.write` regenera o `index.md` do diretório e apensa no
    `log.md` a CADA escrita — contá-los faria toda página parecer volátil.

    Falsificável: removendo qualquer exclusão de `conta_para_estabilidade`,
    a linha correspondente reprova. E a lista é a MESMA que o contrato
    `editorial_stability` declara (cross-check em test_epistemics_toml)."""
    assert conta_para_estabilidade("concepts/x.md") is True
    assert conta_para_estabilidade("index.md") is False
    assert conta_para_estabilidade("concepts/index.md") is False
    assert conta_para_estabilidade("log.md") is False
    assert conta_para_estabilidade("reviews/2026-08.md") is False
    # as constantes existem para o cross-check do contrato — sumir com elas
    # é sumir com a declaração, não com a regra
    assert "index.md" in BASENAMES_REGENERADOS
    assert "reviews/" in PREFIXOS_DE_RITUAL


def test_consolidar_ordena_da_mais_quieta_para_a_mais_volatil():
    """Sem limiar: onde cortar "núcleo" é decisão de leitura. O que o
    kernel garante é ordem determinística (edições asc, empate por caminho)
    e que página sem história sai com ZERO — inventar 1 seria fabricar
    história."""
    historico = {"concepts/volatil.md": {"edicoes": 5, "primeira_em": 1.0,
                                         "ultima_em": 9.0},
                 "concepts/quieta.md": {"edicoes": 1, "primeira_em": 1.0,
                                        "ultima_em": 1.0}}
    frontmatter = {"concepts/volatil.md": {}, "concepts/quieta.md": {},
                   "concepts/sem_historia.md": {}}
    ordem = [e.rel_path for e in consolidar(historico, frontmatter)]
    assert ordem == ["concepts/sem_historia.md", "concepts/quieta.md",
                     "concepts/volatil.md"]


def test_ciclo_vem_de_vitality_e_nao_e_recalculado_aqui():
    """Sentido 2 (ciclo de vida) é LIDO, com o vocabulário de
    `vitality.APOSENTAM` — o campo diz o MOTIVO, não um booleano."""
    frontmatter = {"concepts/viva.md": {},
                   "concepts/sucedida.md": {"superseded_by": "concepts/n.md"}}
    por_pagina = {e.rel_path: e.ciclo for e in consolidar({}, frontmatter)}
    assert por_pagina == {"concepts/viva.md": "viva",
                          "concepts/sucedida.md": "superseded_by"}


def test_historia_de_pagina_que_nao_esta_no_bundle_nao_entra():
    """Página apagada/movida tem história no Git e não é estabilidade de
    coisa nenhuma: o ranking descreve o bundle DE AGORA."""
    historico = {"concepts/fantasma.md": {"edicoes": 3}}
    assert consolidar(historico, {"concepts/real.md": {}}) == [
        Estabilidade("concepts/real.md", 0, None, None, "viva")]


# ====================================== a leitura de história (GitStore)
def test_edit_history_conta_commits_que_tocam_cada_arquivo(settings, kb):
    _escreve(kb, _doc("concepts/a.md", "A"), msg="cria A")
    _escreve(kb, _doc("concepts/b.md", "B"), msg="cria B")
    _edita(kb, _doc("concepts/a.md", "A v2"), msg="edita A")

    hist = GitStore(kb).edit_history()
    assert hist["bundle/concepts/a.md"]["edicoes"] == 2
    assert hist["bundle/concepts/b.md"]["edicoes"] == 1
    a = hist["bundle/concepts/a.md"]
    assert a["primeira_em"] <= a["ultima_em"]
    # o preço declarado da exclusão: o log/index REGENERADOS têm história
    # maior que qualquer página — é exatamente por isso que ficam fora
    assert hist["bundle/log.md"]["edicoes"] >= 3


def test_edit_history_em_repo_sem_head_e_vazio(tmp_path):
    assert GitStore(tmp_path / "novo").edit_history() == {}


# ================================================== a projeção (usecase)
def test_projecao_persiste_ranking_e_registra_checkpoint(settings, kb):
    _escreve(kb, _doc("concepts/a.md", "A"))
    _edita(kb, _doc("concepts/a.md", "A v2"))
    _escreve(kb, _doc("concepts/b.md", "B"))

    resultado = ComputeStability(settings).execute()
    assert resultado["pages"] == 2
    ordem = [e["rel_path"] for e in resultado["stability"]]
    assert ordem == ["concepts/b.md", "concepts/a.md"]   # quieta primeiro

    idx = connect(settings.app_support / "index.db")
    try:
        linhas = {r["rel_path"]: dict(r) for r in idx.execute(
            "SELECT * FROM page_stability")}
    finally:
        idx.close()
    assert linhas["concepts/a.md"]["edits"] == 2
    assert linhas["concepts/b.md"]["edits"] == 1
    assert linhas["concepts/a.md"]["computed_from"] == resultado["head"]
    # o index.md regenerado NÃO aparece — a exclusão chega até a tabela
    assert not any(p.endswith("index.md") for p in linhas)

    # frescor de graça: a derivação declarada aparece FRESH no doctor…
    estado = {v.derivation: v.state for v in verify(settings)}
    assert estado["stability"] == "fresh"

    # …e mover o bundle a torna STALE sem invariante novo. Falsificável:
    # sem o `record()` no use case, o estado seria `absent` e não `stale`.
    _escreve(kb, _doc("concepts/c.md", "C"))
    estado = {v.derivation: v.state for v in verify(settings)}
    assert estado["stability"] == "stale"


def test_projecao_e_deterministica_para_o_mesmo_head(settings, kb):
    _escreve(kb, _doc("concepts/a.md", "A"))
    primeiro = ComputeStability(settings).execute()
    segundo = ComputeStability(settings).execute()
    assert primeiro == segundo


def test_limit_corta_o_retorno_mas_nao_a_persistencia(settings, kb):
    _escreve(kb, _doc("concepts/a.md", "A"), _doc("concepts/b.md", "B"),
             _doc("concepts/c.md", "C"))
    resultado = ComputeStability(settings, limit=1).execute()
    assert resultado["pages"] == 3
    assert len(resultado["stability"]) == 1
    idx = connect(settings.app_support / "index.db")
    try:
        total = idx.execute(
            "SELECT COUNT(*) c FROM page_stability").fetchone()["c"]
    finally:
        idx.close()
    assert total == 3


def test_pagina_aposentada_aparece_com_o_motivo(settings, kb):
    """Aposentar não é apagar (F3-PR2): a página sucedida segue no ranking
    — quem estuda quer saber que o "núcleo estável" dele inclui uma página
    que já foi sucedida — mas carrega o motivo, nunca um booleano mudo."""
    _escreve(kb, _doc("concepts/velha.md", "Velha"),
             _doc("concepts/nova.md", "Nova"))
    _edita(kb, _doc("concepts/velha.md", "Velha",
                    superseded_by="concepts/nova.md"))
    resultado = ComputeStability(settings).execute()
    ciclos = {e["rel_path"]: e["ciclo"] for e in resultado["stability"]}
    assert ciclos["concepts/velha.md"] == "superseded_by"
    assert ciclos["concepts/nova.md"] == "viva"


def test_stability_esta_declarada_na_cadeia_de_derivacoes():
    """`record()` recusa derivação fora de DERIVATIONS — então esta linha é
    o que permite ao use case existir. Fonte: BUNDLE direto (não o índice),
    para a projeção ser 100% re-derivável do canônico."""
    assert DERIVATIONS["stability"] == "bundle"
