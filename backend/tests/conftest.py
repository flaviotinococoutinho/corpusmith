from __future__ import annotations
from pathlib import Path
import pytest
from corpusmith.okf.bootstrap import ensure_bundle
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.git_store import GitStore
from corpusmith.harness.runner import HarnessRunner
from corpusmith.settings import Settings


@pytest.fixture(autouse=True)
def _local_models_offline(monkeypatch) -> None:
    """A suíte é HERMÉTICA: não fala com o Ollama da máquina.

    Sem isto o resultado dependia do que o dev tinha instalado — passava
    em máquina sem Ollama e falhava em máquina com outro conjunto de
    modelos (foi assim que 25 testes ficaram vermelhos com o Ollama de pé
    e o modelo da config ausente). Apontar para uma porta morta exercita
    de forma determinística o caminho de degradação documentado no
    docs/12 §6. Testes que exercitam o roteador substituem `httpx`
    diretamente e ficam imunes a este redirecionamento.
    """
    monkeypatch.setattr("corpusmith.models.router.ModelRouter._ollama_base",
                        lambda self: "http://127.0.0.1:1")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(home=tmp_path / "corpusmith")


@pytest.fixture
def kb(settings: Settings) -> Path:
    kb = settings.path("knowledge")
    ensure_bundle(kb)
    return kb


@pytest.fixture
def bundle(kb: Path) -> Path:
    return kb / "bundle"


@pytest.fixture
def runner(kb: Path, bundle: Path) -> HarnessRunner:
    return HarnessRunner(BundleReader(bundle), GitStore(kb))


def write_page(bundle: Path, rel: str, text: str) -> None:
    p = bundle / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
