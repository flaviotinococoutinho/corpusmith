"""v1.8 (Fase A do plano docs/13): tornar VISÍVEL o sinal já computado.

R1 — grounding por span (kernel puro + evidência do /ask com offsets).
R3 — fila única "Próxima ação" ranqueada por densidade valor/custo,
     unificando revisão, lacunas, inbox, pontes frágeis e contradições.

Nada de cálculo novo: os testes fixam que a projeção é fiel, determinística
e reconstruível (migração aditiva idempotente no index.db).
"""
from __future__ import annotations
from corpusmith.kernel.grounding import ground_spans, MAX_SPANS
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.runtime.db import connect, _migrate, _columns
from corpusmith.usecases.ask_memory import AskMemory
from corpusmith.usecases.next_actions import (NextActions, bridge_items,
                                           contradiction_items, _titleize)


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


# ============================================ R1 · grounding por span (puro)
def test_ground_spans_word_boundary_no_substring_match():
    # "R" não casa dentro de "Rust"; "Rust" casa como palavra inteira
    body = "Rust calcula sinais; Python decide o significado."
    assert ground_spans(body, {"Rust"}) == [[0, 4]]
    assert ground_spans(body, {"R"}) == []             # fronteira de palavra
    spans = ground_spans(body, {"Rust", "Python"})
    assert [body[a:b] for a, b in spans] == ["Rust", "Python"]  # ordenado


def test_ground_spans_accent_and_case_insensitive_preserving_offset():
    body = "A memória Episódica guarda a reflexão."
    # busca sem acento e minúscula deve casar o texto ACENTUADO no offset certo
    spans = ground_spans(body, {"memoria", "episodica"})
    got = [body[a:b] for a, b in spans]
    assert got == ["memória", "Episódica"]             # offsets 1:1 com o original


def test_ground_spans_non_overlapping_longest_wins():
    body = "graph rag e graph"
    spans = ground_spans(body, {"graph", "graph rag"})
    # em 0 começam "graph" e "graph rag"; o mais longo vence e cobre o resto
    assert spans[0] == [0, 9]
    assert body[spans[0][0]:spans[0][1]] == "graph rag"
    assert spans[-1] == [12, 17]                       # o segundo "graph" isolado


def test_ground_spans_empty_and_capped():
    assert ground_spans("", {"x"}) == []
    assert ground_spans("texto", set()) == []
    assert ground_spans("texto", {""}) == []
    big = " ".join(["alfa"] * (MAX_SPANS + 20))
    assert len(ground_spans(big, {"alfa"})) == MAX_SPANS   # teto respeitado


def test_ask_evidence_carries_spans_of_query_entity(settings, kb):
    _write(settings, kb,
           _doc("concepts/uso-pg.md", "Uso de PostgreSQL",
                "# Uso\n\nRodamos PostgreSQL em produção há anos."))
    r = AskMemory(settings, "PostgreSQL", local_only=True).execute()
    ev = next(e for e in r["evidence"] if e["page"] == "concepts/uso-pg.md")
    assert ev["spans"], "a evidência deve localizar a entidade da pergunta"
    body = ev["body"]
    assert any(body[a:b].lower() == "postgresql" for a, b in ev["spans"])


# ================================ R1 · migração aditiva no index.db (5→6)
def test_index_span_migration_is_additive_and_idempotent(tmp_path):
    db = tmp_path / "index.db"
    conn = connect(db)                       # cria já na v6 (colunas presentes)
    assert {"span_start", "span_end"} <= _columns(conn, "page_entities")
    # simula um índice pré-v1.8 (sem as colunas) e migra
    conn.execute("DROP TABLE page_entities")
    conn.execute("CREATE TABLE page_entities(page TEXT, entity_id TEXT, "
                 "surface TEXT, n INTEGER, confidence TEXT, data TEXT)")
    assert "span_start" not in _columns(conn, "page_entities")
    _migrate(conn, "index.db")
    assert {"span_start", "span_end"} <= _columns(conn, "page_entities")
    _migrate(conn, "index.db")               # 2ª vez não pode falhar
    assert {"span_start", "span_end"} <= _columns(conn, "page_entities")
    conn.close()


def test_index_entities_store_spans_on_rebuild(settings, kb):
    _write(settings, kb,
           _doc("concepts/pg2.md", "PostgreSQL de novo",
                "# PG\n\nMigramos para PostgreSQL no ano passado."))
    idx = connect(settings.app_support / "index.db")
    rows = [dict(r) for r in idx.execute(
        "SELECT surface, span_start, span_end FROM page_entities "
        "WHERE page='concepts/pg2.md' AND span_start IS NOT NULL")]
    idx.close()
    assert rows, "o anexo de entidades deve gravar offsets de span"
    assert all(r["span_end"] > r["span_start"] >= 0 for r in rows)


# ==================================== R3 · fila única de próxima ação
def test_titleize_slug_to_phrase():
    assert _titleize("concepts/spaced-repetition.md") == "spaced repetition"
    assert _titleize("a/b_c.md") == "b c"
    assert _titleize("raw/nota.txt") == "nota.txt"     # sem .md, mantém sufixo


def test_next_actions_unifies_sources_and_ranks_by_density(settings, kb):
    # inbox: fonte capturada e não compilada (fonte barata, alto density)
    (kb / "raw").mkdir(parents=True, exist_ok=True)
    (kb / "raw" / "captura.md").write_text("# Nota\n\nalgo a absorver depois.")
    # pergunta aberta (lacuna do Harness)
    _write(settings, kb,
           _doc("concepts/pergunta.md", "Dúvida em aberto",
                "# Dúvida\n\nComo isso funciona?", type="question"))
    out = NextActions(settings).execute()
    assert out["actions"], "a fila não pode vir vazia com inbox+lacuna"
    kinds = {a["kind"] for a in out["actions"]}
    assert {"inbox", "question"} <= kinds
    # todo item traz origem, valor, custo, razão e ação de um clique
    for a in out["actions"]:
        assert a["origin"] and a["reason"] and a["title"]
        assert a["value"] > 0 and a["cost_min"] > 0
        assert "type" in a["action"]
    # ranqueado por densidade valor/custo DESC (o VoI por minuto)
    dens = [a["value"] / a["cost_min"] for a in out["actions"]]
    assert dens == sorted(dens, reverse=True)
    assert out["total"] == len(out["actions"]) or out["truncated"]
    assert sum(out["by_origin"].values()) == out["total"]


def test_next_actions_truncates_with_flag(settings, kb):
    docs = [_doc(f"concepts/q{i}.md", f"Q{i}",
                 f"# Q{i}\n\npergunta número {i}?", type="question")
            for i in range(6)]
    _write(settings, kb, *docs)
    out = NextActions(settings, limit=3).execute()
    assert len(out["actions"]) == 3
    assert out["total"] >= 6 and out["truncated"] is True


def test_bridge_items_reads_persisted_bridges(settings, kb):
    # F3-PR2: as páginas precisam EXISTIR no bundle. Antes o fixture inseria
    # pontes para caminhos inventados e passava — o mesmo buraco que fazia a
    # fila propor trabalho sobre página inexistente em produção.
    _write(settings, kb,
           _doc("concepts/tema-a.md", "Tema A", "# A\n\ntexto."),
           _doc("concepts/tema-b.md", "Tema B", "# B\n\ntexto."))
    idx = connect(settings.app_support / "index.db")
    idx.execute("INSERT OR REPLACE INTO graph_bridges VALUES (?,?,?,?,?)",
                ("concepts/tema-a.md", "concepts/tema-b.md", 0.15, 4, 9))
    idx.commit()
    idx.close()
    items = bridge_items(settings)
    assert len(items) == 1
    it = items[0]
    assert it["kind"] == "bridge"
    assert it["action"] == {"type": "link", "src": "concepts/tema-a.md",
                            "dst": "concepts/tema-b.md"}
    assert "↔" in it["title"] and it["value"] > 0.7   # small_side 4 > base


def test_contradiction_items_flag_same_identifier_without_succession(
        settings, kb):
    doi = "10.1000/xyz123"
    _write(settings, kb,
           _doc("concepts/paper-v1.md", "Paper v1",
                f"# Paper\n\nEstudo com DOI {doi} sobre memória."),
           _doc("concepts/paper-v2.md", "Paper v2",
                f"# Paper\n\nOutra página citando o mesmo DOI {doi}."))
    items = contradiction_items(settings)
    assert items, "mesmo identificador forte em 2 páginas sem sucessão"
    it = items[0]
    assert it["kind"] == "contradiction"
    assert it["action"]["type"] == "resolve-contradiction"
    assert set(it["action"]["pages"]) == {"concepts/paper-v1.md",
                                          "concepts/paper-v2.md"}


def test_cockpit_next_actions_endpoint(settings, kb):
    from fastapi.testclient import TestClient
    from corpusmith.api.system import build_app
    from corpusmith.runtime.events import EventBus
    from corpusmith.runtime.governor import Governor
    from corpusmith.runtime.queue import JobQueue
    (kb / "raw").mkdir(parents=True, exist_ok=True)
    (kb / "raw" / "nota.md").write_text("# Nota\n\nabsorver depois.")
    rt = connect(settings.app_support / "runtime.db")
    connect(settings.app_support / "index.db").close()
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-corpusmith-auth": "t"})
        r = c.get("/cockpit/next-actions?limit=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "actions" in body and "total" in body and "by_origin" in body
    assert len(body["actions"]) <= 5
