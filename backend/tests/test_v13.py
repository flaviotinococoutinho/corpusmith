"""v0.13 (garimpo de repositórios/papers): PPR multi-hop (HippoRAG),
índice incremental (espírito LSM/Arrow), SimHash (Charikar) e páginas
relacionadas (A-mem)."""
from __future__ import annotations
from corpusmith.kernel.graphwalk import personalized_pagerank
from corpusmith.kernel.sketch import hamming, simhash
from corpusmith.facades import CompilerFacade
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.retrieval.related import related_pages
from corpusmith.runtime.db import connect
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


# ------------------------------------------------------- kernel: PPR
def test_ppr_sums_to_one_and_biases_seeds():
    adjacency = {"a": {"b": 1.0}, "b": {"a": 1.0, "c": 1.0}, "c": {"b": 1.0}}
    rank = personalized_pagerank(adjacency, {"a": 1.0})
    assert abs(sum(rank.values()) - 1.0) < 1e-6
    assert rank["a"] > rank["b"] > rank["c"]       # massa decai com a distância
    # multi-hop: c só é alcançável via b, mas recebe massa
    assert rank["c"] > 0.0
    # seed fora do grafo não explode
    assert personalized_pagerank(adjacency, {"zz": 1.0})["zz"] > 0


def test_ppr_damping_controls_locality():
    chain = {f"n{i}": {f"n{i+1}": 1.0} for i in range(5)}
    tight = personalized_pagerank(chain, {"n0": 1.0}, damping=0.2)
    loose = personalized_pagerank(chain, {"n0": 1.0}, damping=0.85)
    assert tight["n0"] > loose["n0"]               # damping baixo prende ao seed
    assert loose["n4"] > tight["n4"]               # damping alto caminha longe


# ---------------------------------------------------- kernel: SimHash
def test_simhash_near_duplicates_and_distinct():
    a = "migramos o banco para postgres rodando em kubernetes ontem à noite"
    b = "migramos o banco para postgres rodando em kubernetes hoje à noite"
    c = "receita de bolo de cenoura com cobertura de chocolate quente"
    assert hamming(simhash(a), simhash(a)) == 0
    assert hamming(simhash(a), simhash(b)) < hamming(simhash(a), simhash(c))
    assert hamming(simhash(a), simhash(c)) > 12
    assert simhash("") == 0


def test_consolidate_clusters_near_duplicates_without_entities(settings, kb):
    raw = kb / "raw"
    base = ("# Plantio\n\nAnotações sobre o plantio de tomates na horta do "
            "quintal durante a primavera, com adubação orgânica semanal.\n")
    (raw / "plantio-1.md").write_text(base)
    (raw / "plantio-2.md").write_text(base.replace("semanal", "quinzenal"))
    result = CompilerFacade(settings).consolidate_inbox()
    assert result["clusters"] == 1                 # via sketch, sem gazetteer


# ------------------------------------------------ índice incremental
def test_incremental_reindexes_only_changed_pages(settings, kb):
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nprimeiro conteúdo"),
           _doc("concepts/b.md", "B", "# B\n\nsegundo conteúdo"))
    idx = connect(settings.app_support / "index.db")
    ids_a_before = [r["id"] for r in idx.execute(
        "SELECT id FROM chunks WHERE page='concepts/a.md'")]
    idx.close()
    # muda só B direto no disco
    (kb / "bundle/concepts/b.md").write_text(
        (kb / "bundle/concepts/b.md").read_text().replace(
            "segundo", "segundo conteúdo REVISADO"))
    report = rebuild_index(settings)
    assert report["mode"] == "incremental"
    assert report["reindexed"] == 1 and report["removed"] == 0
    idx = connect(settings.app_support / "index.db")
    ids_a_after = [r["id"] for r in idx.execute(
        "SELECT id FROM chunks WHERE page='concepts/a.md'")]
    body_b = idx.execute("SELECT text FROM chunks WHERE page='concepts/b.md'"
                         ).fetchone()["text"]
    idx.close()
    assert ids_a_after == ids_a_before             # A intocada (rowids iguais)
    assert "REVISADO" in body_b


def test_incremental_purges_removed_and_full_on_gazetteer_change(settings, kb):
    _write(settings, kb, _doc("concepts/sai.md", "Sai", "# Sai\n\nvai embora"))
    (kb / "bundle/concepts/sai.md").unlink()
    report = rebuild_index(settings)
    assert report["removed"] == 1
    idx = connect(settings.app_support / "index.db")
    assert idx.execute("SELECT COUNT(*) c FROM chunks WHERE "
                       "page='concepts/sai.md'").fetchone()["c"] == 0
    idx.close()
    # authority record novo muda a detecção de TODAS as páginas ⇒ o
    # PRÓXIMO rebuild (sem rebuild intermediário) é full automaticamente
    BundleWriter(kb).write(
        [_doc("authorities/stack/duckdb.md", "DuckDB", "# DuckDB",
              type="authority_record", canonical="DuckDB",
              aliases=["duckdb"], authority="stack")],
        log_kind="Creation", log_message="m", commit_message="c")
    report = rebuild_index(settings)
    assert report["mode"] == "full"
    # e a rodada seguinte volta a ser incremental
    assert rebuild_index(settings)["mode"] == "incremental"


def test_rebuild_com_embeddings_populadas_nao_viola_fk(settings, kb):
    """Regressão da FK `embeddings.chunk_id → chunks(id)`: o rebuild poda
    vetores junto com os chunks — no incremental só os da página purgada;
    no full todos (ids renumerados ⇒ vetor sobrevivente apontaria para
    chunk errado). Sem a poda, editar página com embedding vivo estourava
    IntegrityError e levava o `doctor --repair` junto."""
    _write(settings, kb,
           _doc("concepts/a.md", "A", "# A\n\nprimeiro conteúdo"),
           _doc("concepts/b.md", "B", "# B\n\nsegundo conteúdo"))
    idx = connect(settings.app_support / "index.db")
    ids = {r["page"]: r["id"] for r in
           idx.execute("SELECT page, id FROM chunks")}
    for page in ("concepts/a.md", "concepts/b.md"):
        idx.execute("INSERT INTO embeddings(chunk_id, model, vec) "
                    "VALUES (?,?,?)", (ids[page], "m", b"\x00"))
    idx.commit(); idx.close()
    # incremental: muda só B — vetor de A sobrevive, o de B sai com o chunk
    (kb / "bundle/concepts/b.md").write_text(
        (kb / "bundle/concepts/b.md").read_text().replace(
            "segundo", "segundo conteúdo REVISADO"))
    assert rebuild_index(settings)["mode"] == "incremental"
    idx = connect(settings.app_support / "index.db")
    remaining = [r["chunk_id"] for r in
                 idx.execute("SELECT chunk_id FROM embeddings")]
    idx.close()
    assert remaining == [ids["concepts/a.md"]]
    # full: nenhum vetor pode sobrar
    assert rebuild_index(settings, full=True)["mode"] == "full"
    idx = connect(settings.app_support / "index.db")
    assert idx.execute("SELECT COUNT(*) c FROM embeddings"
                       ).fetchone()["c"] == 0
    idx.close()


# --------------------------------------------- HippoRAG: stream de grafo
def test_graph_stream_reaches_linked_page_multi_hop(settings, kb):
    a = _doc("concepts/uso-postgres.md", "Uso de PostgreSQL",
             "# Uso\n\nUsamos PostgreSQL; detalhes em "
             "[tuning](/concepts/tuning-avancado.md).")
    b = _doc("concepts/tuning-avancado.md", "Tuning avançado",
             "# Tuning avançado\n\nAjustes de work_mem e checkpoints "
             "para cargas pesadas.")
    _write(settings, kb, a, b)
    r = AskMemory(settings, "PostgreSQL", local_only=True).execute()
    pages = [e["page"] for e in r["evidence"]]
    # B não menciona PostgreSQL nem casa com a pergunta no FTS —
    # só o passeio no grafo (PPR) o alcança, via o link de A
    assert "concepts/uso-postgres.md" in pages
    assert "concepts/tuning-avancado.md" in pages


# ------------------------------------------------- A-mem: relacionadas
def test_related_pages_suggest_missing_links(settings, kb):
    a = _doc("concepts/api-grpc.md", "API gRPC",
             "# API\n\nUsamos gRPC e RabbitMQ no backbone.")
    b = _doc("concepts/mensageria.md", "Mensageria",
             "# Mensageria\n\nRabbitMQ e gRPC conectam os serviços.")
    linked = _doc("concepts/ja-linkada.md", "Já linkada",
                  "# Já linkada\n\ngRPC também aqui; ver "
                  "[api](/concepts/api-grpc.md).")
    _write(settings, kb, a, b, linked)
    related = related_pages(settings, "concepts/api-grpc.md")
    pages = [r["page"] for r in related]
    assert "concepts/mensageria.md" in pages       # compartilha, não linka
    assert "concepts/ja-linkada.md" not in pages   # já linkada: excluída
    assert set(related[0]["shared"]) >= {"gRPC"}


# ----------------------------------------------- v0.14: lacunas fechadas
def test_promoted_page_is_immediately_askable(settings, kb):
    from corpusmith.facades import CurationFacade
    CurationFacade(settings).promote(
        kind="semantic", title="Baleias jubarte",
        content="As baleias jubarte migram para águas quentes no inverno.")
    r = AskMemory(settings, "baleias jubarte", local_only=True).execute()
    assert not r["abstained"]                       # sem rebuild manual
    assert r["evidence"][0]["page"] == "concepts/baleias-jubarte.md"


def test_stale_flag_reaches_index_immediately(settings, kb):
    from corpusmith.facades import CurationFacade
    CurationFacade(settings).promote(
        kind="semantic", title="Antiga técnica",
        content="técnica antiga de cache")
    CurationFacade(settings).mark_stale("concepts/antiga-tecnica.md")
    r = AskMemory(settings, "técnica antiga de cache",
                  local_only=True).execute()
    assert r["evidence"][0]["stale"] is True        # sem rebuild manual


def test_recycle_refuses_when_page_is_live_again(settings, kb):
    import pytest as _pytest
    import time as _time
    from corpusmith.facades import CurationFacade
    from corpusmith.usecases.cold_memory import RecycleMemory
    CurationFacade(settings).promote(
        kind="semantic", title="Repromovida", content="versão um")
    rt = connect(settings.app_support / "runtime.db")
    old = _time.time() - 200 * 86_400
    rt.execute("INSERT OR REPLACE INTO page_heat"
               "(path, reads, last_seen, first_seen) VALUES (?,1,?,?)",
               ("concepts/repromovida.md", old, old - 86_400))
    rt.commit(); rt.close()
    CurationFacade(settings).freeze("concepts/repromovida.md")
    # repromove no MESMO slug (conteúdo novo, mais atual que o congelado)
    CurationFacade(settings).promote(
        kind="semantic", title="Repromovida", content="versão dois, atual")
    with _pytest.raises(KeyError, match="quente"):
        RecycleMemory(settings, "concepts/repromovida.md").execute()
    # a entrada fria obsoleta foi purgada e o conteúdo novo está intacto
    assert CurationFacade(settings).cold()["count"] == 0
    assert "versão dois" in (kb / "bundle/concepts/repromovida.md").read_text()


def test_jobs_list_includes_payload_for_retry(settings, kb):
    from corpusmith.runtime.queue import JobQueue
    rt = connect(settings.app_support / "runtime.db")
    queue = JobQueue(rt)
    queue.enqueue("compile_source", {"path": "raw/x.md"})
    job = queue.list()[0]
    rt.close()
    assert job["payload"] == {"path": "raw/x.md"}   # habilita reexecutar
