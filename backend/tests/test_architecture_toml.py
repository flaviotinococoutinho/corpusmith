"""v1.5 — `architecture.toml` NÃO pode divergir do código (spec §18.1).

Cruza o contrato legível-por-máquina com as MESMAS constantes que
`test_architecture.py` aplica ao código real. Se alguém editar um sem o
outro, a suíte quebra — a doc de arquitetura fica presa à realidade.
"""
from __future__ import annotations
import tomllib
from pathlib import Path
import test_architecture as arch

_TOML = Path(__file__).resolve().parents[2] / "architecture.toml"


def _load() -> dict:
    return tomllib.loads(_TOML.read_text())


def test_toml_exists_and_parses():
    assert _TOML.is_file()
    assert _load()["schema_version"] == 1


def test_toml_pure_forbidden_matches_enforced_set():
    spec = set(_load()["pure"]["forbidden_imports"])
    assert spec == arch.FORBIDDEN_IN_PURE            # espelho exato
    assert set(_load()["pure"]["packages"]) == set(arch.PURE_PACKAGES)


def test_toml_transport_matches_enforced_set():
    spec = set(_load()["domain"]["forbidden_imports"])
    assert spec == arch.TRANSPORT
    assert set(_load()["domain"]["packages"]) == set(arch.DOMAIN_PACKAGES)


def test_toml_product_version_matches_package():
    from corpusmith import __version__
    assert _load()["product_version"] == __version__  # versão única


def test_toml_databases_match_schema_versions():
    from corpusmith.runtime.db import SCHEMA_VERSIONS
    declared = {d["name"]: d["schema_version"]
                for d in _load()["database"]}
    assert declared == SCHEMA_VERSIONS               # nem sobra, nem falta


# ============================== invariantes: um dono, provas que existem
import re as _re

_ROOT = _TOML.parent
_TESTS = Path(__file__).resolve().parent


def _teste_existe(ref: str) -> bool:
    arquivo, _, funcao = ref.partition("::")
    path = _TESTS / arquivo
    if not path.is_file():
        return False
    return (not funcao or _re.search(rf"^def {_re.escape(funcao)}\(",
                                     path.read_text(), _re.M) is not None)


def test_invariantes_do_toml_sao_os_do_agents():
    """AGENTS.md §4 é a tabela que o agente lê; architecture.toml é o dono.
    Divergir (id a mais num lado) é a entropia que a duplicação convida."""
    agents = (_ROOT / "AGENTS.md").read_text()
    no_agents = set(_re.findall(r"\| (INV-[A-Z]+-\d{3}) \|", agents))
    no_toml = {i["id"] for i in _load()["invariant"]}
    assert no_toml == no_agents, (
        f"só no TOML: {sorted(no_toml - no_agents)}; "
        f"só no AGENTS §4: {sorted(no_agents - no_toml)}")


def test_todo_invariante_e_verificado_por_teste_que_existe():
    """'Verificado por: harness/local_policy.py' era um selo sobre um
    arquivo que não verifica nada — a coluna cita TESTES, e eles existem."""
    fantasmas = [(i["id"], ref) for i in _load()["invariant"]
                 for ref in i["verified_by"] if not _teste_existe(ref)]
    assert fantasmas == [], f"invariante citando teste inexistente: {fantasmas}"
    sem_prova = [i["id"] for i in _load()["invariant"] if not i["verified_by"]]
    assert sem_prova == []
