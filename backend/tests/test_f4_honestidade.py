"""F4-PR1 (ADR-52) — os números epistêmicos param de mentir.

P-9: valid_at sem default de escrita (tempo de MUNDO ≠ tempo de registro).
P-4: `support` ao lado de `uncertainty` — base rasa deixa de virar
certeza máxima."""
from __future__ import annotations
from corpusmith.okf.bundle import BundleReader
from corpusmith.usecases.compile_source import CompileSource
from corpusmith.usecases.ask_memory import AskMemory
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index


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


# ===================================== P-9: valid_at é tempo de MUNDO
def test_pagina_de_maquina_nao_ganha_valid_at_de_brinde(settings, kb):
    """`valid_at = now` na escrita colapsava o eixo de mundo no de
    registro — toda página nascia "válida desde agora", e o `as_of`
    filtrava sobre um carimbo sem significado."""
    (kb / "raw" / "nota.md").write_text(
        "# Fato\n\nO datacenter usa PostgreSQL 16 desde o ano passado.\n")
    CompileSource(settings, "raw/nota.md").execute()
    reader = BundleReader(kb / "bundle")
    pagina = next(d for d in reader.iter_concepts()
                  if "nota" in d.rel_path or "fato" in d.rel_path.lower())
    meta = pagina.meta.model_dump(exclude_none=True)
    assert "timestamp" in meta, "o registro continua carimbado"
    assert "valid_at" not in meta, \
        "valid_at fabricado na escrita — tempo de mundo ≠ tempo de registro"


def test_pagina_sem_valid_at_e_valida_em_qualquer_as_of(settings, kb):
    """A ausência declara 'sem informação de vigência' — o filtro já
    tratava assim (not va ⇒ passa); o teste prende a semântica."""
    _write(settings, kb,
           _doc("concepts/atemporal.md", "Atemporal",
                "# Atemporal\n\nUm fato sobre golfinhos e ecolocalização."))
    r = AskMemory(settings, "golfinhos", local_only=True,
                  as_of="2020-01-01").execute()
    assert any("atemporal" in e["page"] for e in r["evidence"])


def test_valid_at_fornecido_continua_respeitado(settings, kb):
    _write(settings, kb,
           _doc("concepts/datado.md", "Datado",
                "# Datado\n\nContrato com fornecedor de nuvem vigente.",
                valid_at="2025-06-01"))
    meta = BundleReader(kb / "bundle").load("concepts/datado.md") \
        .meta.model_dump(exclude_none=True)
    assert str(meta["valid_at"])[:10] == "2025-06-01"


# ===================================== P-4: support ≠ uncertainty
def test_base_rasa_tem_support_baixo_mesmo_com_certeza_maxima(settings, kb):
    """O defeito medido do P-4: um único chunk ⇒ entropia 0 ⇒
    uncertainty 0 — certeza máxima no momento mais fraco. O `support`
    nasce para dizer a verdade que o outro número esconde."""
    _write(settings, kb,
           _doc("concepts/unico.md", "Único",
                "# Único\n\nSó esta página menciona zeppelins."))
    r = AskMemory(settings, "zeppelins", local_only=True).execute()
    assert r["uncertainty"] <= 0.05          # o número antigo: "certeza"
    assert "support" in r, "o /ask não publica o support (P-4)"
    s = r["support"]
    assert s["score"] <= 0.5, f"base rasa com support alto: {s}"
    assert set(s["components"]) == {"distinct_pages",
                                    "corroborating_streams",
                                    "grounded_fraction", "freshness"}


def test_abstencao_publica_support_zero_com_shape_estavel(settings, kb):
    _write(settings, kb, _doc("concepts/algo.md", "Algo", "# Algo\n\nx."))
    r = AskMemory(settings, "quasar barions", local_only=True).execute()
    assert r["abstained"] is True
    assert r["support"]["score"] == 0.0
