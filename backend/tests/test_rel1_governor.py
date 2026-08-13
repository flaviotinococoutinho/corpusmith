"""REL-1 (P0 do backlog v1.3): todo caminho de modelo que PODE gastar
API carrega o Governor — jobs nunca furam orçamento nem ledger.

Aceite do backlog: gov injetado; ledger reflete compile; teste. A fiação
é worker → JobContext.gov → adapter → facade → usecase → ModelRouter."""
from __future__ import annotations
import time
import pytest
from corpusmith.facades.compiler import CompilerFacade
from corpusmith.runtime.db import connect
from corpusmith.runtime.events import EventBus
from corpusmith.runtime.governor import Governor
from corpusmith.runtime.queue import JobQueue
from corpusmith.runtime.slots import Slots
from corpusmith.runtime.worker import JobContext, Worker
from corpusmith.usecases.compile_source import CompileSource
from corpusmith.usecases.consolidate_inbox import ConsolidateInbox, _ConsolidatedPage
from corpusmith.usecases.detect_communities import DetectCommunities


@pytest.fixture
def rt(settings):
    db = connect(settings.app_support / "runtime.db")
    yield db
    db.close()


@pytest.fixture
def gov(settings, rt):
    return Governor(settings, rt)


# ------------------------------------------------------------ contexto do job
def test_jobcontext_carrega_o_governor(rt, gov):
    ctx = JobContext(EventBus(rt), "j1", "trace", JobQueue(rt), gov=gov)
    assert ctx.gov is gov


def test_worker_entrega_o_governor_aos_handlers(settings, rt, gov, monkeypatch):
    """Fiação real: um job de sonda roda no Worker e enxerga ctx.gov."""
    from corpusmith.jobs import REGISTRY
    seen: dict = {}

    def probe(s, payload, emit):
        seen["gov"] = getattr(emit, "gov", None)
        return {}

    monkeypatch.setitem(REGISTRY, "probe_gov", probe)
    queue = JobQueue(rt)
    jid = queue.enqueue("probe_gov", {})
    worker = Worker(settings, queue, EventBus(rt), gov, Slots())
    worker.start()
    deadline = time.time() + 10
    while time.time() < deadline:
        row = rt.execute("SELECT state FROM jobs WHERE id=?", (jid,)).fetchone()
        if row and row["state"] in ("done", "failed", "dead_lettered"):
            break
        time.sleep(0.05)
    worker.stop()
    worker.join(timeout=5)
    assert row and row["state"] == "done"
    assert seen["gov"] is gov


# ------------------------------------------------- usecases da família compile
def test_compile_source_injeta_gov_no_router(settings, gov):
    uc = CompileSource(settings, "raw/x.md", gov=gov)
    assert uc._router is not None and uc._router.gov is gov


def test_consolidated_page_injeta_gov_no_router(settings, gov):
    uc = _ConsolidatedPage(settings, cluster=[], gov=gov)
    assert uc._router is not None and uc._router.gov is gov


def test_detect_communities_injeta_gov_no_router(settings, gov):
    uc = DetectCommunities(settings, gov=gov)
    assert uc._router.gov is gov


# ------------------------------------------------------------ facade e adapters
def test_facade_propaga_gov_ao_compile(settings, gov, monkeypatch):
    captured: dict = {}

    class Spy:
        def __init__(self, s, path, notify=None, *, gov=None):
            captured["gov"] = gov

        def execute(self):
            return {}

    monkeypatch.setattr("corpusmith.facades.compiler.CompileSource", Spy)
    CompilerFacade(settings, gov=gov).compile("raw/x.md")
    assert captured["gov"] is gov


@pytest.mark.parametrize("module,method", [
    ("corpusmith.jobs.compile", "compile"),
    ("corpusmith.jobs.consolidate", "consolidate_inbox"),
    ("corpusmith.jobs.leiden", "detect_communities"),
])
def test_adapters_leem_gov_do_contexto(settings, monkeypatch, module, method):
    import importlib
    mod = importlib.import_module(module)
    captured: dict = {}

    class SpyFacade:
        def __init__(self, s, gov=None):
            captured["gov"] = gov

        def __getattr__(self, name):
            assert name == method
            return lambda *a, **k: {}

    monkeypatch.setattr(f"{module}.CompilerFacade", SpyFacade)

    class Ctx:
        gov = "governor-sentinela"

        def __call__(self, *a, **k):
            pass

    mod.run(settings, {"path": "x"}, Ctx())
    assert captured["gov"] == "governor-sentinela"


def test_adapter_ask_le_gov_do_contexto(settings, monkeypatch):
    from corpusmith.jobs import ask as ask_job
    captured: dict = {}

    class SpyFacade:
        def __init__(self, s, gov=None):
            captured["gov"] = gov

        def ask(self, *a, **k):
            return {}

    monkeypatch.setattr("corpusmith.jobs.ask.MemoryFacade", SpyFacade)

    class Ctx:
        gov = "governor-sentinela"

        def __call__(self, *a, **k):
            pass

    ask_job.run(settings, {"query": "q"}, Ctx())
    assert captured["gov"] == "governor-sentinela"


# ----------------------------------------------------- ledger reflete compile
def test_ledger_registra_gasto_quando_router_tem_gov(settings, rt, gov,
                                                     monkeypatch):
    """Com o gov injetado, a chamada de API do caminho de compile grava
    no ledger e o orçamento diário enxerga o gasto (aceite REL-1)."""
    from corpusmith.models.router import ModelRouter

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{"text": "resumo"}]}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-teste")
    monkeypatch.setattr("corpusmith.models.router.httpx.post",
                        lambda *a, **k: FakeResp())
    router = ModelRouter(settings, gov)
    out = router._api("prompt", None, 64)
    assert out["via"].startswith("api:") and out["usd"] > 0
    row = rt.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(usd),0) usd FROM ledger").fetchone()
    assert row["c"] == 1 and row["usd"] == pytest.approx(out["usd"])
    assert gov.spent_today() == pytest.approx(out["usd"])
