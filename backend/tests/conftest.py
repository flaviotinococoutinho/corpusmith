from __future__ import annotations
from pathlib import Path
import pytest
from llmwiki.okf.bootstrap import ensure_bundle
from llmwiki.okf.bundle import BundleReader
from llmwiki.okf.git_store import GitStore
from llmwiki.harness.runner import HarnessRunner
from llmwiki.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(home=tmp_path / "llmwiki")


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
