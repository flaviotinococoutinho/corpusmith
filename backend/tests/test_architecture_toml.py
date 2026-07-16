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
    from llmwiki import __version__
    assert _load()["product_version"] == __version__  # versão única


def test_toml_databases_match_schema_versions():
    from llmwiki.runtime.db import SCHEMA_VERSIONS
    declared = {d["name"]: d["schema_version"]
                for d in _load()["database"]}
    assert declared == SCHEMA_VERSIONS               # nem sobra, nem falta
