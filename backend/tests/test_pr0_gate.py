"""PR-0 (v1.8.1) — o INSTRUMENTO antes da obra (docs/15 §2).

O plano de execução (docs/15) constatou que dez pacotes prometem "gate
completo: pytest + tsc + compose + epistemics lint" enquanto a CI executa
pytest, tsc+vite, compose e cargo — nunca `epistemics lint`, nunca
`doctor`. Um DoD que ninguém verifica não é um DoD.

Estes testes fecham quatro lacunas de PROCESSO (G-1, G-4, G-6, G-9):
- o gate passa a ter UMA fonte (`architecture.toml [gate]`), cruzada com
  o ci.yml e com o justfile — como architecture.toml e epistemics.toml já
  são cruzados com o código;
- a migração de schema ganha prova de UPGRADE (hoje `_migrate` decide por
  presença de coluna e nada prova que um banco antigo chega íntegro);
- `bench compare --against` ganha semântica testada de regressão de RAZÃO;
- a versão deixa de divergir entre os artefatos que a declaram.
"""
from __future__ import annotations
import json
import re
import sqlite3
import tomllib
from pathlib import Path
import pytest
from llmwiki import __version__
from llmwiki.bench import DEFAULT_TOLERANCE, compare_against
from llmwiki.runtime.db import SCHEMA_VERSIONS, _columns, connect, \
    reset_initialized

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).parent / "fixtures"


def _arch() -> dict:
    return tomllib.loads((_ROOT / "architecture.toml").read_text())


# ============================== G-9 · o gate tem UMA fonte
def _ci_runs() -> str:
    """Todas as linhas `run:` do ci.yml concatenadas — nas duas formas que
    o YAML permite (`- run: x` e `- name: …` + `run: x`)."""
    ci = (_ROOT / ".github/workflows/ci.yml").read_text()
    return "\n".join(re.findall(r"^\s*-?\s*run:\s*(.+)$", ci, re.M))


def _verify_recipe() -> str:
    """Corpo da receita `verify` do justfile (linhas indentadas)."""
    lines = (_ROOT / "justfile").read_text().splitlines()
    out, inside = [], False
    for line in lines:
        if re.match(r"^verify\b.*:", line):
            inside = True
            continue
        if inside:
            if line and not line[0].isspace():
                break
            out.append(line)
    return "\n".join(out)


def test_ci_executa_todo_o_gate_declarado():
    """G-1: cada token de [gate].ci_enforced tem de aparecer num `run:`
    do ci.yml. Falhava antes: epistemics lint e doctor não existiam lá."""
    runs = _ci_runs()
    faltando = [t for t in _arch()["gate"]["ci_enforced"] if t not in runs]
    assert not faltando, (
        f"a CI não executa parte do gate declarado: {faltando} — "
        "um DoD que promete 'gate completo' fica sem prova")


def test_verify_do_justfile_cobre_o_gate_estatico():
    recipe = _verify_recipe()
    faltando = [t for t in _arch()["gate"]["verify_enforced"]
                if t not in recipe]
    assert not faltando, (
        f"`just verify` não cobre: {faltando} — quem roda o atalho vê "
        "verde sem ter rodado o gate")


def test_agents_md_nao_finge_contagem_de_testes():
    """A doc normativa do gate dizia '# 345 testes' com a suíte em 389.
    Número fixo em doc apodrece; o gate não pode mentir sobre si."""
    agents = (_ROOT / "AGENTS.md").read_text()
    assert not re.search(r"#\s*\d{3,}\s+testes", agents), (
        "AGENTS.md §2 voltou a cravar uma contagem de testes — ela deriva "
        "no primeiro PR que adiciona um teste")


# ============================== G-6 · migração com prova de UPGRADE
def test_upgrade_de_index_antigo_preserva_dados_e_carimba(tmp_path):
    """`_migrate` decide por presença de COLUNA, nunca por versão — a
    única prova de que o upgrade funciona é abrir um banco que de fato
    não tem as colunas. Exercita as três migrações do index.db de uma vez."""
    db = tmp_path / "index.db"
    raw = sqlite3.connect(db)
    raw.row_factory = sqlite3.Row          # _columns() lê r["name"]
    raw.executescript((_FIXTURES / "schema_index_pre_migrations.sql")
                      .read_text())
    raw.execute("INSERT INTO chunks(page, ord, text) "
                "VALUES ('concepts/a.md', 0, 'corpo antigo')")
    raw.execute("INSERT INTO graph_edges(src, dst, kind) "
                "VALUES ('concepts/a.md', 'concepts/b.md', 'markdown')")
    raw.execute("INSERT INTO entities(id, kind, canonical) "
                "VALUES (1, 'stack', 'Rust')")
    raw.execute("INSERT INTO page_entities(page, entity_id, surface) "
                "VALUES ('concepts/a.md', 1, 'Rust')")
    raw.execute("CREATE TABLE IF NOT EXISTS _meta("
                "key TEXT PRIMARY KEY, value TEXT)")
    raw.execute("INSERT INTO _meta(key, value) VALUES ('schema_version','3')")
    raw.commit()
    # o banco antigo REALMENTE não tem as colunas (senão o teste é vazio)
    assert "confidence" not in _columns(raw, "graph_edges")
    assert "span_start" not in _columns(raw, "page_entities")
    assert "superseded" not in _columns(raw, "chunks")
    raw.close()

    reset_initialized()
    idx = connect(db)                      # deve migrar 3 → versão corrente
    try:
        wanted = SCHEMA_VERSIONS["index.db"]
        # (a) colunas novas presentes
        assert "confidence" in _columns(idx, "graph_edges")
        assert {"span_start", "span_end"} <= _columns(idx, "page_entities")
        assert {"valid_at", "invalid_at", "superseded"} <= _columns(idx,
                                                                   "chunks")
        # (b) dados preservados
        assert idx.execute("SELECT text FROM chunks WHERE page='concepts/a.md'"
                           ).fetchone()["text"] == "corpo antigo"
        assert idx.execute("SELECT COUNT(*) c FROM graph_edges"
                           ).fetchone()["c"] == 1
        assert idx.execute("SELECT surface FROM page_entities"
                           ).fetchone()["surface"] == "Rust"
        # (c) carimbo final e (d) trilha auditável do upgrade
        assert int(idx.execute("SELECT value FROM _meta WHERE "
                               "key='schema_version'").fetchone()["value"]) \
            == wanted
        trail = idx.execute("SELECT from_version, to_version FROM "
                            "schema_migrations ORDER BY id").fetchall()
        assert (3, wanted) in [(r["from_version"], r["to_version"])
                               for r in trail]
    finally:
        idx.close()
        reset_initialized()


def test_reabrir_banco_migrado_nao_reaplica_migracao(tmp_path):
    """Idempotência: a segunda abertura não acrescenta linha ao ledger."""
    db = tmp_path / "index.db"
    reset_initialized()
    connect(db).close()
    reset_initialized()
    idx = connect(db)
    n = idx.execute("SELECT COUNT(*) c FROM schema_migrations"
                    ).fetchone()["c"]
    idx.close()
    reset_initialized()
    idx = connect(db)
    assert idx.execute("SELECT COUNT(*) c FROM schema_migrations"
                       ).fetchone()["c"] == n
    idx.close()
    reset_initialized()


# ============================== G-4 · o baseline vira autoridade executável
def _compare_result(ppr: float, brandes: float) -> dict:
    return {"product_version": __version__,
            "graph": {"speedup": {"ppr": ppr, "brandes": brandes}},
            "consolidate": {}}


def test_compare_against_detecta_regressao_de_razao(tmp_path):
    """Tolerância EXPLÍCITA: o teste fixa a semântica do piso, não o valor
    do default (que é frouxo de propósito — ver o teste seguinte)."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({
        "product_version": __version__,
        "graph_5000n_20000e": {"speedup": {"ppr": 100.0, "brandes": 40.0}}}))
    # dentro da tolerância de 25%: 80 ≥ 100×0.75 ⇒ sem regressão
    ok = compare_against(_compare_result(80.0, 40.0), baseline,
                         tolerance=0.25)
    assert ok["comparable"] and ok["regressions"] == []
    # abaixo do piso ⇒ regressão nomeada
    bad = compare_against(_compare_result(50.0, 40.0), baseline,
                          tolerance=0.25)
    assert bad["regressions"] == ["graph.ppr"]
    piso = {r["metric"]: r["floor"] for r in bad["ratios"]}
    assert piso["graph.ppr"] == 75.0 and piso["graph.brandes"] == 30.0


def test_tolerancia_default_e_frouxa_e_nao_esta_no_gate_por_pr():
    """Razão é quociente, e o denominador pode ser ~2 ms (PPR em Rust):
    medido, trocar de máquina derrubou `graph.ppr` 30% sem mudar código
    (Python 15% mais rápido, Rust 21% mais lento). Default frouxo pega
    COLAPSO de razão; e `bench` fica fora de [gate].ci_enforced porque é
    guarda de mesma-máquina, não de PR."""
    assert DEFAULT_TOLERANCE >= 0.4
    assert not any("bench" in t for t in _arch()["gate"]["ci_enforced"])


def test_compare_against_sem_extensao_nativa_nao_finge_verde(tmp_path):
    """Sem Rust não há razão a comparar — o veredito diz isso em voz alta
    em vez de passar em silêncio (a camada nativa é opcional por ADR-39)."""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({
        "product_version": __version__,
        "graph_5000n_20000e": {"speedup": {"ppr": 100.0}}}))
    v = compare_against({"product_version": __version__, "graph": {},
                         "consolidate": {}}, baseline)
    assert v["comparable"] is False and v["reason"]
    assert v["regressions"] == []


def test_baseline_real_declara_versao_e_razoes():
    """O baseline do repo é a autoridade citada pelos ADRs: precisa ter
    razões declaradas e uma versão de captura (que pode estar ATRÁS do
    produto — carimbo histórico honesto, não erro)."""
    baseline = json.loads((_ROOT / "benchmarks/baseline.json").read_text())
    assert baseline.get("product_version")
    assert baseline["graph_5000n_20000e"]["speedup"]["brandes"] > 1
    assert baseline["consolidate_440docs"]["speedup"]["sketch"] > 1


# ============================== versão: uma fonte para os artefatos
def test_versao_unica_entre_produto_arquitetura_e_app():
    """`test_architecture_toml` já amarra architecture.toml ↔ __version__;
    desktop/package.json ficava solto (estava em 0.7.0 com produto 1.8.0)."""
    pkg = json.loads((_ROOT / "desktop/package.json").read_text())
    assert _arch()["product_version"] == __version__ == pkg["version"]


def test_baseline_nao_vem_do_futuro():
    """Medição carimbada com versão MAIOR que a do produto é impossível —
    seria alegação de ganho não reproduzível (AGENTS.md §6)."""
    def parts(v: str) -> tuple:
        return tuple(int(x) for x in v.split(".")[:3])
    baseline = json.loads((_ROOT / "benchmarks/baseline.json").read_text())
    assert parts(baseline["product_version"]) <= parts(__version__)


# ============================== G-2 · a perna [ml] existe e é declarada
def test_marcador_ml_declarado_no_pyproject():
    """O ramo Leiden de PRODUÇÃO (igraph/leidenalg) só é exercitado com o
    extra [ml]; sem marcador declarado, `pytest -m ml` é erro de config."""
    pyproject = tomllib.loads(
        (_ROOT / "backend/pyproject.toml").read_text())
    markers = pyproject["tool"]["pytest"]["ini_options"].get("markers", [])
    assert any(m.startswith("ml:") for m in markers)


def test_ci_tem_perna_ml():
    runs = _ci_runs()
    assert "dev,ml" in runs and "-m ml" in runs, (
        "sem a perna [ml] o algoritmo de particionamento que de fato roda "
        "em produção nunca é executado por teste (verde-por-skip)")
