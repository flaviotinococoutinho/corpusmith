"""Checkpoints normalizados: o estado entre as fontes e a cadeia (ADR-46).

**O problema é medido nesta árvore.** `bundle_head` aparecia em QUATRO lugares
— `index_meta`, `graph_snapshot.bundle_head`, `theme_epochs.bundle_head` e o
schema de runtime — e cada derivação precisou do próprio invariante no doctor:
INV-002 (índice), INV-004 (mapa), INV-005 (temas).

O custo não é estético. Foi essa dispersão que deixou passar o defeito
confirmado por execução na auditoria: o job `leiden` escrevia páginas (movendo
o HEAD) e o índice ficava atrás, e **nada relacionava as duas coisas** — o
carimbo do mapa se dizia fresco enquanto o do índice apodrecia.

O teste que justifica o pacote inteiro é
`test_obsolescencia_transitiva_e_o_caso_que_carimbo_isolado_nao_pega`: uma
derivação coerente com a fonte IMEDIATA e ainda assim servindo dado velho
porque a fonte da fonte mudou. Nenhum carimbo isolado consegue ver isso, por
construção — só a cadeia declarada.
"""
from __future__ import annotations
import pytest
from corpusmith.kernel.checkpoints import (DERIVATIONS, Checkpoint, ancestors,
                                        descendants, evaluate)
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.checkpoints import load, record, verify
from corpusmith.runtime.db import SCHEMA_VERSIONS, connect
from corpusmith.usecases.detect_communities import DetectCommunities
from corpusmith.usecases.diagnose import DiagnoseSystem


# ============================================== a cadeia (puro)
def test_a_cadeia_e_um_dag_com_uma_autoridade():
    """`bundle` é a única fonte sem fonte — canônico ≠ projeção posto em
    estrutura de dados, não em comentário."""
    raizes = [d for d, fonte in DERIVATIONS.items() if fonte is None]
    assert raizes == ["bundle"]
    for d in DERIVATIONS:
        assert "bundle" in ancestors(d) or d == "bundle", d


def test_ancestrais_e_descendentes_fecham_a_cadeia():
    assert ancestors("themes") == ["graph_map", "index", "bundle"]
    assert ancestors("bundle") == []
    # mexer no índice obsoleta tudo que vem depois
    assert set(descendants("index")) == {"graph_map", "centrality", "themes"}
    assert descendants("themes") == []


def test_toda_derivacao_declarada_tem_fonte_conhecida():
    """Guarda contra o erro fácil de acrescentar derivação apontando para
    fonte que não existe — aí a cadeia mente em silêncio."""
    for d, fonte in DERIVATIONS.items():
        assert fonte is None or fonte in DERIVATIONS, f"{d} -> {fonte}"


# ============================================== os três vereditos
def _cp(nome, estado):
    return Checkpoint(nome, estado, 1.0)


def test_derivacao_ausente_nao_e_defeito():
    """Instalação nova não tem derivação VELHA, tem derivação NENHUMA —
    acusar isso viraria ruído em todo doctor recém-instalado (mesma razão do
    INV-004)."""
    v = {x.derivation: x for x in evaluate({}, {"bundle": "abc"})}
    assert v["index"].state == "absent"
    assert v["bundle"].state == "fresh"


def test_derivacao_coerente_com_a_fonte_e_fresca():
    v = {x.derivation: x for x in evaluate(
        {"index": _cp("index", "abc")}, {"bundle": "abc"})}
    assert v["index"].state == "fresh" and v["index"].ok


def test_fonte_imediata_mudou_e_stale():
    v = {x.derivation: x for x in evaluate(
        {"index": _cp("index", "abc")}, {"bundle": "def"})}
    assert v["index"].state == "stale"
    assert "abc" in v["index"].reason and "def" in v["index"].reason


def test_obsolescencia_transitiva_e_o_caso_que_carimbo_isolado_nao_pega():
    """O TESTE QUE JUSTIFICA O PACOTE.

    O mapa está coerente com o índice — o carimbo dele, sozinho, diz "fresco".
    Mas o índice está atrás do bundle. Nenhum carimbo isolado enxerga isso: o
    do mapa compara com o índice e acha tudo bem; o do índice compara com o
    bundle e reclama de si. Só a CADEIA declarada relaciona os dois.

    É exatamente a forma do defeito confirmado por execução na auditoria."""
    cps = {"index": _cp("index", "antigo"),
           "graph_map": _cp("graph_map", "antigo"),
           "themes": _cp("themes", "antigo")}
    atual = {"bundle": "NOVO", "index": "antigo", "graph_map": "antigo"}
    v = {x.derivation: x for x in evaluate(cps, atual)}
    assert v["index"].state == "stale", "o índice está atrás do bundle"
    assert v["graph_map"].state == "stale_upstream", (
        "o mapa é coerente com o índice e AINDA ASSIM serve dado velho")
    assert v["themes"].state == "stale_upstream", "e a cadeia propaga"
    assert "índice" in v["graph_map"].reason or \
        "index" in v["graph_map"].reason


def test_derivacoes_irmas_nao_se_contaminam():
    """`graph_map` e `centrality` derivam as duas do índice. Uma velha não
    torna a outra velha — só ancestral contamina, não irmão."""
    cps = {"index": _cp("index", "x"),
           "graph_map": _cp("graph_map", "ANTIGO"),
           "centrality": _cp("centrality", "x")}
    v = {y.derivation: y for y in evaluate(cps, {"bundle": "x", "index": "x"})}
    assert v["graph_map"].state == "stale"
    assert v["centrality"].state == "fresh", "irmã contaminou irmã"


# ============================================== persistência
def test_runtime_migra_para_9_aditivamente(settings):
    assert SCHEMA_VERSIONS["runtime.db"] >= 9
    rt = connect(settings.app_support / "runtime.db")
    tabelas = {r["name"] for r in rt.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    rt.close()
    assert "checkpoints" in tabelas
    assert {"curation_acts", "page_heat", "events"} <= tabelas


def test_registro_recusa_derivacao_nao_declarada(settings):
    """Registro dinâmico faria o doctor deixar de conhecer a cadeia — que é
    justamente o que este pacote existe para impedir."""
    with pytest.raises(ValueError, match="não declarada"):
        record(settings, "inventada", "abc")


def test_registro_e_idempotente_por_derivacao(settings):
    record(settings, "index", "aaa", {"pages": 1})
    record(settings, "index", "bbb", {"pages": 2})
    cps = load(settings)
    assert len(cps) == 1 and cps["index"].input_state == "bbb"


def test_o_checkpoint_sobrevive_ao_rebuild_do_indice(settings, kb):
    """A razão de a tabela morar em runtime.db e não em index.db: um carimbo
    sobre o índice que morre junto com o índice não consegue dizer que a
    derivação sumiu. É o limite do `index_meta.bundle_head` de hoje."""
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/a.md", body="# A\n\nx.",
                     meta=OKFFrontMatter(type="concept", title="A",
                                         privacy="local_only",
                                         generated_via="human:promote"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    assert "index" in load(settings), "o rebuild não registrou o checkpoint"
    (settings.app_support / "index.db").unlink()
    assert "index" in load(settings), (
        "o checkpoint morreu junto com o índice que ele descreve")


# ============================================== ponta a ponta
@pytest.fixture
def base(settings, kb):
    docs = []
    for b in range(3):
        for i in range(4):
            viz = "\n".join(f"- [b{b} p{j}](/concepts/b{b}-p{j}.md)"
                            for j in range(4) if j != i)
            fio = (f"\n- [b{b+1} p0](/concepts/b{b+1}-p0.md)"
                   if i == 0 and b + 1 < 3 else "")
            docs.append(OKFDocument(
                rel_path=f"concepts/b{b}-p{i}.md",
                body=f"# b{b} p{i}\n\n{viz}{fio}\n",
                meta=OKFFrontMatter(type="concept", title=f"b{b} p{i}",
                                    privacy="local_only",
                                    generated_via="human:promote")))
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    return settings


def test_o_job_registra_as_tres_derivacoes_que_produz(base):
    DetectCommunities(base).execute()
    cps = load(base)
    assert {"index", "graph_map", "centrality", "themes"} <= set(cps)
    # as três do job derivam do ÍNDICE, e do MESMO estado dele
    estados = {cps[d].input_state
               for d in ("graph_map", "centrality", "themes")}
    assert len(estados) == 1, "as irmãs discordam sobre o estado da fonte"
    assert estados == {cps["index"].input_state}


def test_cadeia_fresca_depois_do_job(base):
    DetectCommunities(base).execute()
    assert all(v.state in ("fresh", "absent") for v in verify(base)), \
        [(v.derivation, v.state, v.reason) for v in verify(base)]


def test_commit_no_bundle_obsoleta_a_cadeia_inteira(base, kb):
    """O caso real: o usuário escreve uma página e não reindexa. O índice
    fica atrás, e o mapa e os temas herdam isso — em vez de três alarmes
    desconexos, uma cadeia com um elo nomeado."""
    DetectCommunities(base).execute()
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/nova.md", body="# Nova\n\nx.",
                     meta=OKFFrontMatter(type="concept", title="Nova",
                                         privacy="local_only",
                                         generated_via="human:promote"))],
        log_kind="Creation", log_message="m", commit_message="c")
    estados = {v.derivation: v.state for v in verify(base)}
    assert estados["index"] == "stale"
    assert estados["graph_map"] == "stale_upstream"
    assert estados["themes"] == "stale_upstream"
    # e o doctor diz isso com UMA regra
    rel = DiagnoseSystem(base).execute()
    inv006 = [f for f in rel["findings"] if f["inv"] == "INV-006"]
    assert inv006, "o doctor não viu a cadeia obsoleta"
    assert all(f["severity"] == "warn" for f in inv006), (
        "derivação velha é servível com aviso, não corrupção")
    assert any("CADEIA" in f["detail"] for f in inv006)


def test_o_doctor_expoe_a_cadeia_inteira(base):
    DetectCommunities(base).execute()
    rel = DiagnoseSystem(base).execute()
    cadeia = rel["derivations"]
    assert set(cadeia) == set(DERIVATIONS)
    assert cadeia["bundle"]["source"] is None
    assert cadeia["themes"]["source"] == "graph_map"
    assert cadeia["index"]["computed_at"]


# ============ achado de auditoria CONFIRMADO por execução (embeddings x FK)
def test_embedding_vivo_nao_quebra_o_reindex(settings, kb):
    """`embeddings.chunk_id REFERENCES chunks(id)` é a ÚNICA FK do index.db, e
    `PRAGMA foreign_keys=ON` a torna dura. Apagar `chunks` com um embedding
    vivo levantava `IntegrityError`.

    Não é hipótese: o job `embed` — que o Scheduler enfileira DIARIAMENTE —
    popula a tabela, e a partir daí qualquer edição de página quebrava o
    reindex. Pior, quebrava o `doctor --repair`, que é o caminho de
    recuperação: o conserto do produto ficava inalcançável.

    Um embedding de chunk inexistente é lixo por definição, então apagá-lo
    junto é a semântica correta, não um contorno."""
    import sqlite3
    doc = OKFDocument(rel_path="concepts/e.md", body="# E\n\ncorpo.",
                      meta=OKFFrontMatter(type="concept", title="E",
                                          privacy="local_only",
                                          generated_via="human:promote"))
    BundleWriter(kb).write([doc], log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    assert idx.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    cid = idx.execute("SELECT id FROM chunks LIMIT 1").fetchone()["id"]
    idx.execute("INSERT INTO embeddings(chunk_id, model, vec) VALUES (?,?,?)",
                (cid, "nomic-embed-text", b"vetor"))
    idx.commit()
    idx.close()
    # incremental (editar a página) e full (o caminho do doctor --repair)
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/e.md", body="# E\n\nCORPO NOVO.",
                     meta=doc.meta)],
        log_kind="Update", log_message="m2", commit_message="c2")
    try:
        rebuild_index(settings)
        rebuild_index(settings, full=True)
    except sqlite3.IntegrityError as e:
        pytest.fail(f"a FK de embeddings quebrou o reindex: {e}")


def test_doctor_repair_sobrevive_a_embedding_vivo(settings, kb):
    """O caminho de RECUPERAÇÃO tem de funcionar justamente quando há dado —
    um reparo que só roda em banco vazio não é reparo."""
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/e.md", body="# E\n\ncorpo.",
                     meta=OKFFrontMatter(type="concept", title="E",
                                         privacy="local_only",
                                         generated_via="human:promote"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    idx = connect(settings.app_support / "index.db")
    cid = idx.execute("SELECT id FROM chunks LIMIT 1").fetchone()["id"]
    idx.execute("INSERT INTO embeddings(chunk_id, model, vec) VALUES (?,?,?)",
                (cid, "nomic-embed-text", b"v"))
    idx.commit()
    idx.close()
    rel = DiagnoseSystem(settings, repair=True).execute()
    assert not [f for f in rel["findings"] if f["severity"] == "error"], rel
