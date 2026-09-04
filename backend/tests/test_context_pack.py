"""O context pack (docs/10 §18.4) — determinístico e fiel às fontes.

Um mapa gerado só vale mais que a prosa copiada se (1) duas execuções
sobre o mesmo HEAD produzem o mesmo mapa, (2) cada seção é IGUAL à fonte
que ela diz ler, e (3) o comando existe de verdade no CLI e no justfile.
Sem o teste, `docs/10 §18.4 ✅` seria mais um selo sobre um arquivo.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pytest

from corpusmith import __version__
from corpusmith.context_pack import (REPO_ROOT, NaoEhUmCheckout, build,
                                     render, to_json)

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pack() -> dict:
    return build()


def test_raiz_detectada_e_o_repositorio():
    assert REPO_ROOT == _ROOT
    assert (REPO_ROOT / "architecture.toml").is_file()


def test_fora_de_um_checkout_falha_alto(tmp_path):
    with pytest.raises(NaoEhUmCheckout):
        build(tmp_path)


def test_duas_execucoes_produzem_o_mesmo_mapa(pack):
    assert to_json(build()) == to_json(pack)


def test_produto_e_head(pack):
    assert pack["product"]["version"] == __version__
    assert re.fullmatch(r"[0-9a-f]{7,}|unknown", pack["product"]["head"])


def test_jobs_sao_os_do_registry(pack):
    """AST/regex do fonte contra o import real: se o REGISTRY mudar de
    forma, a leitura do mapa quebra aqui antes de mentir."""
    from corpusmith.jobs import REGISTRY
    assert pack["jobs"] == sorted(REGISTRY)


def test_rotas_sao_as_do_fonte(pack):
    """Cada rota do mapa está literalmente num decorator de api/; e o
    inventário é o mesmo que `test_pontas_soltas` mede."""
    from test_pontas_soltas import _rotas
    assert pack["endpoints"] == sorted({f"{m} {r}" for m, r, _ in _rotas()})
    assert len(pack["endpoints"]) > 50


def test_use_cases_sao_as_classes_reais(pack):
    from corpusmith.usecases.ask_memory import AskMemory
    from corpusmith.usecases.concept_sheet import ConceptSheet
    assert {AskMemory.__name__, ConceptSheet.__name__} <= set(pack["use_cases"])


def test_registros_batem_com_os_loaders(pack):
    from corpusmith.harness.epistemics import lint
    from corpusmith.harness.ontology import overview
    e, o = lint(), overview()
    assert pack["registries"]["epistemics"]["mechanisms"] == e["mechanisms"]
    assert pack["registries"]["epistemics"]["version"] == e["registry_version"]
    assert pack["registries"]["ontology"]["terms"] == len(o["terms"])
    assert pack["registries"]["ontology"]["axes"] == len(o["axes"])


def test_bancos_derivacoes_e_eventos_vem_das_constantes(pack):
    from corpusmith.kernel.checkpoints import DERIVATIONS
    from corpusmith.runtime.db import SCHEMA_VERSIONS
    from corpusmith.runtime.events import EVENT_TYPES
    assert pack["databases"] == SCHEMA_VERSIONS
    assert pack["derivations"] == DERIVATIONS
    assert pack["events"] == sorted(EVENT_TYPES)


def test_invariantes_e_nfrs_vem_dos_tomls(pack):
    import tomllib
    arch = tomllib.loads((_ROOT / "architecture.toml").read_text())
    nfr = tomllib.loads((_ROOT / "nfr.toml").read_text())
    assert [i["id"] for i in pack["invariants"]] == \
        [i["id"] for i in arch["invariant"]]
    assert [n["id"] for n in pack["nfr"]["items"]] == \
        [n["id"] for n in nfr["nfr"]]
    assert sum(pack["nfr"]["by_status"].values()) == len(nfr["nfr"])


def test_adrs_sao_os_headings_de_docs08(pack):
    ids = [a["id"] for a in pack["adrs"]]
    assert "ADR-53" in ids and "ADR-38" in ids
    assert len(ids) == len(set(ids)), "ADR duplicado em docs/08"


def test_todo_doc_esta_no_mapa_com_altitude_e_status(pack):
    arquivos = sorted(p.name for p in (_ROOT / "docs").glob("*.md"))
    assert [d["file"] for d in pack["docs"]] == arquivos
    sem = [d["file"] for d in pack["docs"] if not d["altitude"] or not d["status"]]
    assert sem == [], f"docs sem cabeçalho legível pelo mapa: {sem}"


def test_fila_corrente_le_a_secao_11(pack):
    b = pack["backlog"]
    assert b["section"] == "docs/18 §11"
    assert not (set(b["open"]) & set(b["closed"]))


def test_nenhuma_linha_da_fila_e_largada_em_silencio(pack):
    """O parser tem que VER toda linha `| Q-n |` da §11.

    Medido ao fechar a Q-1: pôr o ✅ na PRIMEIRA célula (`| **Q-1** ✅ |`)
    faz `_BACKLOG_ROW` não casar, e o item desaparece do mapa — nem
    aberto nem fechado. O mapa continuava "verde" enquanto perdia um item,
    que é a falha silenciosa que este arquivo existe para impedir. A
    contagem por regex frouxa é a testemunha independente da regex
    estrita do produto."""
    secao = re.search(r"^## 11\..*?(?=^## |\Z)",
                      (_ROOT / "docs/18-backlog-consolidado.md").read_text(),
                      re.S | re.M).group(0)
    citados = {m.group(1) for m in
               re.finditer(r"^\|\s*\**(Q-\d+)\b", secao, re.M)}
    vistos = set(pack["backlog"]["open"]) | set(pack["backlog"]["closed"])
    assert citados == vistos, (
        "linhas da fila que o mapa não enxerga: "
        f"{sorted(citados - vistos)} — o ✅ vai na SEGUNDA coluna")


def test_render_e_markdown_completo(pack):
    md = render(pack)
    for titulo in ("## Camadas", "## Gate", "## Invariantes",
                   "## Requisitos não funcionais", "## Registros",
                   "## Endpoints", "## ADRs", "## Documentos",
                   "## Fila corrente"):
        assert titulo in md
    assert "None" not in md


def test_cli_context_imprime_json_valido(capsys, tmp_path):
    from corpusmith.cli import cmd_context
    from corpusmith.settings import Settings
    assert cmd_context(Settings(home=tmp_path),
                       argparse.Namespace(json=True)) == 0
    saida = json.loads(capsys.readouterr().out)
    assert saida["product"]["version"] == __version__


def test_justfile_tem_a_receita_context():
    """docs/10 §18.4 pedia `just context`: a receita existe e chama o
    mesmo comando que o teste acima exercita."""
    just = (_ROOT / "justfile").read_text()
    assert re.search(r"^context:\n\s+.*corpusmith\.cli context", just, re.M)
