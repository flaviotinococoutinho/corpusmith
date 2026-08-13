"""v0.16 — requisitos não funcionais executáveis: identidade snowflake,
configuração versionada (ring de 30 + rollback com guard de fitness),
health API profunda, HATEOAS e seleção adaptativa de algoritmo na
consolidação (pares ↔ índice invertido + LSH exato)."""
from __future__ import annotations
import random
import pytest
from fastapi.testclient import TestClient
from corpusmith.api.system import build_app
from corpusmith.kernel import identity
from corpusmith.kernel.sketch import BITS, bands, hamming
from corpusmith.runtime.db import connect
from corpusmith.runtime.events import EventBus
from corpusmith.runtime.governor import Governor
from corpusmith.runtime.queue import JobQueue
from corpusmith.settings import Settings
from corpusmith.usecases.configure_system import (HISTORY_LIMIT, RollbackConfig,
                                               TuneConfig, config_history)


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-corpusmith-auth": "t"})
        yield c


# ================================================== identidade snowflake
def test_snowflake_roundtrip_carries_module_algorithm_and_time():
    factory = identity.SnowflakeFactory("ask", "rrf")
    sid = factory.next_id()
    parsed = identity.parse(sid)
    assert parsed["module"] == "ask"
    assert parsed["algorithm"] == "rrf"
    assert parsed["ts_ms"] >= identity.EPOCH_MS
    # render/unrender é bijetivo e o texto decodifica igual ao inteiro
    assert identity.unrender(identity.render(sid)) == sid
    assert identity.parse(identity.render(sid)) == parsed


def test_snowflake_ids_are_unique_and_monotonic_under_burst():
    factory = identity.SnowflakeFactory("job")
    ids = [factory.next_id() for _ in range(5000)]
    assert len(set(ids)) == 5000
    assert ids == sorted(ids)                    # timestamp nos bits altos
    rendered = [identity.render(i) for i in ids]
    assert rendered == sorted(rendered)          # ordem lexicográfica = temporal


def test_snowflake_clock_regression_never_repeats():
    factory = identity.SnowflakeFactory()
    first = factory.next_id(now_ms=identity.EPOCH_MS + 10_000)
    second = factory.next_id(now_ms=identity.EPOCH_MS + 5_000)  # relógio p/ trás
    assert second > first                        # clamp: segue monotônico


def test_snowflake_sequence_overflow_advances_logical_ms():
    factory = identity.SnowflakeFactory()
    now = identity.EPOCH_MS + 1
    ids = [factory.next_id(now_ms=now) for _ in range(1100)]  # > 1024 no mesmo ms
    assert len(set(ids)) == 1100
    assert identity.parse(ids[-1])["ts_ms"] > identity.parse(ids[0])["ts_ms"]


def test_shared_factory_prevents_cross_instance_collision():
    a = identity.factory("compile")
    b = identity.factory("compile")
    assert a is b


# ============================================ bandas LSH (casa de pombos)
def test_lsh_bands_guarantee_every_near_duplicate_pair():
    """Propriedade, não exemplo: QUALQUER par com hamming ≤ 8 compartilha
    ao menos uma das 9 bandas — a geração de candidatos é exata."""
    rng = random.Random(42)
    for _ in range(300):
        base = rng.getrandbits(BITS)
        flips = rng.sample(range(BITS), rng.randint(0, 8))
        other = base
        for bit in flips:
            other ^= 1 << bit
        assert hamming(base, other) <= 8
        assert set(bands(base, count=9)) & set(bands(other, count=9)), \
            f"par near-duplicata sem banda comum: {base:x} vs {other:x}"


def test_lsh_bands_cover_all_64_bits():
    zero, ones = bands(0, count=9), bands((1 << BITS) - 1, count=9)
    assert not set(zero) & set(ones)             # todo bit pertence a uma banda


# ================================= consolidação: seleção adaptativa exata
def test_candidate_pairs_indexed_mode_equals_pairwise(settings):
    from corpusmith.usecases.consolidate_inbox import ConsolidateInbox, _Signature

    class _Stub:                                  # assinatura sintética
        NEAR_DUPLICATE_HAMMING = _Signature.NEAR_DUPLICATE_HAMMING

        def __init__(self, ids, ents, sketch):
            self.strong_ids, self.entities, self.sketch = ids, ents, sketch

    rng = random.Random(7)
    pending = []
    for i in range(60):
        ids = {f"doi:10.1000/{i % 9}"} if i % 4 == 0 else set()
        ents = {f"Ent{i % 13}", f"Ent{(i * 3) % 13}"} if i % 3 else set()
        pending.append(_Stub(ids, ents, rng.getrandbits(64)))
    uc = ConsolidateInbox(settings, min_shared=1, min_cluster=2)
    indexed = set(uc._candidate_pairs(pending))            # n=60 > 32: índice
    uc_small = ConsolidateInbox(settings, min_shared=1, min_cluster=2)
    uc_small._pairwise_max = 10_000
    exhaustive = set(uc_small._candidate_pairs(pending))   # força pares
    # todo par que converge de fato tem de estar entre os candidatos
    converging = {(i, j) for i, j in exhaustive
                  if _Signature.converges_with(pending[i], pending[j], 1)}
    assert converging <= indexed


# ================================ configuração versionada: ring + rollback
def test_tune_records_history_and_ring_evicts_beyond_30(settings):
    TuneConfig(settings, {"ask": {"abstain_threshold": 0.01}}).execute()
    rows = config_history(settings)
    assert rows[0]["changes"] == {"ask": {"abstain_threshold": 0.01}}
    assert rows[-1]["source"] == "baseline"      # geração-zero gravada antes
    for i in range(40):                          # estoura o ring
        TuneConfig(settings, {"consolidate": {"min_shared": i + 1}}).execute()
    rows = config_history(settings, limit=100)
    assert len(rows) == HISTORY_LIMIT
    assert rows[0]["snapshot"]["consolidate"]["min_shared"] == 40
    assert all(r["source"] != "baseline" for r in rows)   # a mais velha caiu


def test_rollback_returns_to_previous_generation(settings):
    TuneConfig(settings, {"memory": {"min_idle_days": 10}}).execute()
    TuneConfig(settings, {"memory": {"min_idle_days": 55}}).execute()
    assert settings.get("memory.min_idle_days") == 55
    result = RollbackConfig(settings).execute()
    assert settings.get("memory.min_idle_days") == 10
    assert result["snapshot"]["memory"]["min_idle_days"] == 10
    rows = config_history(settings)
    assert rows[0]["source"] == "rollback"       # o retorno é nova geração


def test_rollback_without_history_refuses(settings):
    with pytest.raises(ValueError):
        RollbackConfig(settings).execute()


def test_tune_rejects_wrong_type_and_unknown_key_without_side_effects(settings):
    before = settings.snapshot()
    with pytest.raises(ValueError):
        TuneConfig(settings, {"memory": {"min_idle_days": True}}).execute()
    with pytest.raises(ValueError):
        TuneConfig(settings, {"memory": {"dias": 3}}).execute()
    with pytest.raises(ValueError):
        TuneConfig(settings, {"server": {"port": 1}}).execute()  # não ajustável
    assert settings.snapshot() == before
    assert config_history(settings) == []        # variação inviável nem nasce


def test_new_flags_are_allowed_but_must_be_boolean(settings):
    TuneConfig(settings, {"flags": {"retrieval.experimental": True}}).execute()
    assert settings.flag("retrieval.experimental") is True
    with pytest.raises(ValueError):
        TuneConfig(settings, {"flags": {"outra.flag": "sim"}}).execute()


# ============================================= contratos: health + HATEOAS
def test_root_is_a_hateoas_map_without_auth(client):
    r = client.get("/", headers={"x-corpusmith-auth": "errado"})
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "corpusmith"
    assert {"health_full", "config_rollback", "dashboard"} <= set(body["_links"])
    assert body["_links"]["config"]["href"] == "/cockpit/config"


def test_health_full_requires_auth_and_reports_deep_state(client):
    assert client.get("/health/full",
                      headers={"x-corpusmith-auth": "errado"}).status_code == 401
    r = client.get("/health/full").json()
    assert r["ok"] is True
    assert r["instance"]["module"] == "daemon"   # snowflake decodificado
    assert r["stacks"]["runtime.db"]["integrity"] == "ok"
    assert "jobs" in r["stacks"]["runtime.db"]["tables"]
    assert r["resources"]["disk_free_mb"] > 0
    assert "by_state" in r["queue"]
    assert "_links" in r


def test_config_endpoints_are_navigable_and_versioned(client):
    got = client.get("/cockpit/config").json()
    assert got["_links"]["rollback"]["href"] == "/cockpit/config/rollback"
    set1 = client.post("/cockpit/config",
                       json={"ask": {"abstain_threshold": 0.02}}).json()
    assert set1["ask"]["abstain_threshold"] == 0.02
    assert set1["trace_id"]                       # ajuste tem identidade
    client.post("/cockpit/config", json={"ask": {"abstain_threshold": 0.5}})
    hist = client.get("/cockpit/config/history").json()["history"]
    assert hist[0]["snapshot"]["ask"]["abstain_threshold"] == 0.5
    back = client.post("/cockpit/config/rollback")
    assert back.status_code == 200
    assert back.json()["snapshot"]["ask"]["abstain_threshold"] == 0.02
    bad = client.post("/cockpit/config", json={"ask": {"abstain_threshold": "x"}})
    assert bad.status_code == 400


def test_rollback_on_virgin_history_is_409(client):
    assert client.post("/cockpit/config/rollback").status_code == 409


# ==================================================== tracing ponta a ponta
def test_ask_id_is_a_decodable_trace(settings, kb):
    from corpusmith.facades import MemoryFacade
    from corpusmith.okf.document import OKFDocument, OKFFrontMatter
    from corpusmith.okf.writer import BundleWriter
    from corpusmith.retrieval.fts import rebuild_index
    BundleWriter(kb).write(
        [OKFDocument(rel_path="concepts/kafka.md", body="# Kafka\n\nfilas.",
                     meta=OKFFrontMatter(type="concept", title="Kafka",
                                         privacy="local_only"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)
    r = MemoryFacade(settings).ask("Kafka filas", local_only=True)
    parsed = identity.parse(r["ask_id"])
    assert parsed["module"] == "ask" and parsed["algorithm"] == "rrf"
    assert r["identity"]["module"] == "ask"


def test_machine_page_stages_share_one_trace(settings, kb):
    from corpusmith.usecases.base import DraftPage, MachinePageUseCase
    seen = []

    class _Page(MachinePageUseCase):
        MODULE = "compile"

        def _produce(self):
            return DraftPage(rel_path="concepts/span.md", title="Span",
                             body="# Span\n\ncorpo.")

    _Page(settings, notify=lambda t, d: seen.append((t, d))).execute()
    stages = [d for t, d in seen if t == "page.stage"]
    assert [s["stage"] for s in stages] == \
        ["produce", "normalize", "reconcile", "write", "done"]
    traces = {s["trace_id"] for s in stages}
    assert len(traces) == 1                       # UMA execução, UM trace
    assert identity.parse(traces.pop())["module"] == "compile"
    spans = [s["span"] for s in stages]
    assert len(set(spans)) == len(spans)          # cada stage, um span
    assert spans == sorted(spans)                 # spans ordenam no tempo
