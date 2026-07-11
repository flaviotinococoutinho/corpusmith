"""v0.18 — camada cognitiva: calibração (Brier), economia de atenção
(4p(1−p) + mochila gulosa), estado declarado com TTL, resposta adaptativa
(estratégia Hedge + orçamento CLT), metacognição com gate humano cujo
aceite passa pela linhagem de configuração."""
from __future__ import annotations
import json
import time
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.kernel.attention import fill_budget, review_gain
from llmwiki.kernel.calibration import (brier_score, calibration_bins,
                                        overconfidence)
from llmwiki.facades import CognitionFacade, MemoryFacade
from llmwiki.okf.document import OKFDocument, OKFFrontMatter
from llmwiki.okf.writer import BundleWriter
from llmwiki.retrieval.fts import rebuild_index
from llmwiki.runtime.db import connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue
from llmwiki.usecases.cognitive_state import (DeclareCognitiveState,
                                              STRATEGIES, current_state,
                                              delivery_budget)
from llmwiki.usecases.configure_system import config_history
from llmwiki.usecases.metacognition import ObserveMetacognition


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": "t"})
        yield c


def _seed_page(settings, kb, rel="concepts/kafka.md", title="Kafka",
               body="# Kafka\n\nKafka processa filas de eventos.",
               type="concept"):
    BundleWriter(kb).write(
        [OKFDocument(rel_path=rel, body=body,
                     meta=OKFFrontMatter(type=type, title=title,
                                         privacy="local_only"))],
        log_kind="Creation", log_message="m", commit_message="c")
    rebuild_index(settings)


# ============================================================= kernel
def test_brier_and_overconfidence_known_values():
    assert brier_score([]) is None
    assert brier_score([(1.0, 1), (0.0, 0)]) == 0.0        # calibração perfeita
    assert brier_score([(1.0, 0)]) == 1.0                  # pior caso
    assert overconfidence([(0.9, 0), (0.9, 1)]) == pytest.approx(0.4)
    bins = calibration_bins([(0.1, 0), (0.9, 1), (0.95, 0)], bins=5)
    assert bins[0]["n"] == 1 and bins[-1]["n"] == 2
    assert bins[-1]["hit_rate"] == 0.5


def test_review_gain_peaks_at_productive_effort():
    assert review_gain(0.5) == 1.0                         # pico
    assert review_gain(0.05) < 0.2 and review_gain(0.98) < 0.1
    assert review_gain(-1) == 0.0 and review_gain(2) == 0.0


def test_fill_budget_is_greedy_by_density_and_respects_budget():
    items = [{"target": "a", "value": 1.0, "cost_min": 10},
             {"target": "b", "value": 0.9, "cost_min": 3},
             {"target": "c", "value": 0.2, "cost_min": 2},
             {"target": "d", "value": 0.5, "cost_min": 0}]   # custo 0: fora
    plan = fill_budget(items, budget_min=14)
    assert [i["target"] for i in plan] == ["b", "c", "a"][:len(plan)]
    assert sum(i["cost_min"] for i in plan) <= 14
    small = fill_budget(items, budget_min=14, max_item_cost=5)
    assert {i["target"] for i in small} == {"b", "c"}


# ================================================ estado declarado (TTL)
def test_declared_state_wins_then_expires_to_neutral(settings):
    assert current_state(settings)["declared"] is False    # neutro
    DeclareCognitiveState(settings, load=5, focus=2,
                          time_available_min=30).execute()
    state = current_state(settings)
    assert state["load"] == 5 and state["declared"] is True
    rt = connect(settings.app_support / "runtime.db")      # envelhece a força
    rt.execute("UPDATE cognitive_state SET ts = ts - 9 * 3600")
    rt.commit(); rt.close()
    assert current_state(settings)["declared"] is False    # TTL 8h venceu
    with pytest.raises(ValueError):
        DeclareCognitiveState(settings, load=9).execute()


def test_delivery_budget_follows_cognitive_load(settings):
    assert delivery_budget(settings, 5)["evidence_limit"] == 5
    assert delivery_budget(settings, 5)["concise"] is True
    assert delivery_budget(settings, 3)["max_tokens"] == 1024
    assert delivery_budget(settings, 1)["max_tokens"] == 1536


# ================================================== resposta adaptativa
def test_ask_records_strategy_load_and_confidence(settings, kb):
    _seed_page(settings, kb)
    DeclareCognitiveState(settings, load=5).execute()
    r = MemoryFacade(settings).ask("Kafka filas", local_only=True)
    assert r["strategy"] in STRATEGIES
    assert r["cognitive"] == {"load": 5, "declared": True}
    rt = connect(settings.app_support / "runtime.db")
    row = rt.execute("SELECT strategy, load, confidence FROM ask_context "
                     "WHERE ask_id = ?", (r["ask_id"],)).fetchone()
    rt.close()
    assert row["strategy"] == r["strategy"] and row["load"] == 5
    assert 0.0 <= row["confidence"] <= 1.0


def test_declared_profile_beats_observed_strategy(settings, kb):
    _seed_page(settings, kb)
    settings.profile["preferred_strategy"] = "teoria-primeiro"
    r = MemoryFacade(settings).ask("Kafka filas", local_only=True)
    assert r["strategy"] == "teoria-primeiro"              # FR-14.3


def test_outcome_trains_strategy_credit(settings, kb):
    _seed_page(settings, kb)
    settings.profile["preferred_strategy"] = "decomposicao"
    r = MemoryFacade(settings).ask("Kafka filas", local_only=True)
    MemoryFacade(settings).record_outcome(
        verdict="useful", ask_id=r["ask_id"],
        pages=[e["page"] for e in r["evidence"]])
    rt = connect(settings.app_support / "runtime.db")
    weight = rt.execute("SELECT weight FROM strategy_weights "
                        "WHERE strategy = 'decomposicao'").fetchone()["weight"]
    rt.close()
    assert weight > 1.0                                    # útil ⇒ ganhou


# ===================================================== metacognição
def _seed_history(settings, *, strategy="analogia-primeiro", n_good=6,
                  n_bad_other=6, high_load_bad=0, prefix=""):
    """Semeia ask_context+ask_outcomes direto (histórico sintético)."""
    rt = connect(settings.app_support / "runtime.db")
    rows = []
    for i in range(n_good):
        rows.append((f"{prefix}g{i}", strategy, 2, 0.9, "useful"))
    for i in range(n_bad_other):
        rows.append((f"{prefix}b{i}", "direta", 2, 0.9, "dead_end"))
    for i in range(high_load_bad):
        rows.append((f"{prefix}h{i}", "direta", 5, 0.9, "dead_end"))
    for ask_id, strat, load, conf, verdict in rows:
        rt.execute("INSERT INTO ask_context VALUES (?,?,?,?)",
                   (ask_id, strat, load, conf))
        rt.execute("INSERT INTO ask_outcomes(ask_id, verdict, pages) "
                   "VALUES (?,?, '[]')", (ask_id, verdict))
    rt.commit(); rt.close()


def test_observation_mining_needs_support_and_dedupes(settings):
    _seed_history(settings, n_good=2, n_bad_other=2)       # < min_support
    assert ObserveMetacognition(settings).execute()["created"] == 0
    _seed_history(settings, n_good=6, n_bad_other=6, prefix="x")
    first = ObserveMetacognition(settings).execute()
    assert first["created"] >= 1
    again = ObserveMetacognition(settings).execute()
    assert again["created"] == 0                           # dedupe


def test_accepting_observation_applies_suggestion_via_lineage(settings):
    _seed_history(settings)
    CognitionFacade(settings).observe()
    proposed = CognitionFacade(settings).observations("proposed")
    strategy_obs = next(o for o in proposed if o["kind"] == "strategy")
    assert "n=" in strategy_obs["statement"]               # número junto da frase
    result = CognitionFacade(settings).review_observation(
        strategy_obs["id"], "accepted")
    assert result["applied"]["history_id"]
    # o observado virou DECLARADO, com geração na linhagem (source=metacog)
    assert settings.get("profile.preferred_strategy") == "analogia-primeiro"
    assert config_history(settings)[0]["source"] == "metacog"
    with pytest.raises(KeyError):
        CognitionFacade(settings).review_observation(9999, "rejected")
    with pytest.raises(ValueError):
        CognitionFacade(settings).review_observation(
            strategy_obs["id"], "delete")


def test_calibration_report_reflects_history(settings):
    _seed_history(settings, n_good=0, n_bad_other=8)       # confiante e errado
    report = CognitionFacade(settings).overview()["calibration"]
    assert report["n"] == 8
    assert report["overconfidence"] == pytest.approx(0.9)
    assert report["brier"] > 0.5


# ================================================ economia de atenção
def test_attention_plan_reviews_gaps_and_inbox_with_reasons(settings, kb):
    _seed_page(settings, kb)
    _seed_page(settings, kb, rel="questions/aberta.md", title="Aberta?",
               body="# Aberta\n\npendente.", type="question")
    # esquenta kafka num ponto de esforço produtivo (uso antigo)
    rt = connect(settings.app_support / "runtime.db")
    rt.execute("INSERT INTO page_heat(path, reads, first_seen, last_seen) "
               "VALUES ('concepts/kafka.md', 2, ?, ?)",
               (time.time() - 40 * 86400, time.time()))
    rt.commit(); rt.close()
    (kb / "raw").mkdir(exist_ok=True)
    (kb / "raw" / "nota.md").write_text("uma nota curta pendente")
    plan = CognitionFacade(settings).attention_plan(minutes=60)
    kinds = {i["kind"] for i in plan["plan"]}
    assert "question" in kinds and "inbox" in kinds
    assert all(i["reason"] for i in plan["plan"])
    assert sum(i["cost_min"] for i in plan["plan"]) <= 60


def test_attention_under_high_load_prefers_small_blocks(settings, kb):
    _seed_page(settings, kb)
    (kb / "raw").mkdir(exist_ok=True)
    (kb / "raw" / "grande.md").write_text("palavra " * 6000)  # ~40 min
    DeclareCognitiveState(settings, load=5).execute()
    plan = CognitionFacade(settings).attention_plan(minutes=120)
    assert plan["high_load"] is True
    assert all(i["cost_min"] <= 15 for i in plan["plan"])


# ============================================================== HTTP
def test_http_contract_state_cognition_attention(client):
    bad = client.post("/cockpit/state", json={"load": 7})
    assert bad.status_code == 400
    ok = client.post("/cockpit/state",
                     json={"load": 4, "time_available_min": 45})
    assert ok.json()["declared"] is True
    view = client.get("/cockpit/cognition").json()
    assert view["state"]["load"] == 4
    assert set(view["strategies"]) == set(STRATEGIES)
    assert view["calibration"]["n"] == 0
    assert view["_links"]["attention"]["href"] == "/cockpit/attention"
    plan = client.get("/cockpit/attention").json()
    assert plan["budget_min"] == 45                        # veio do estado
    assert client.post("/cockpit/cognition/observations/review",
                       json={"id": 1, "action": "accepted"}).status_code == 404
