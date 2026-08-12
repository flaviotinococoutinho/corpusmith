"""v0.19 — domínio cognitivo PURO: propriedades e goldens, sem nenhuma
infraestrutura (nem Settings): só dados entram, só dados saem."""
from __future__ import annotations
import random
import pytest
from llmwiki.cognitive import (DEFAULT_POLICY, KnowledgeItemView,
                               build_working_set, cognitive_priority,
                               hard_gates, new_focus_goal, new_session,
                               resume_session, schedule_review,
                               suspend_session, update_accessibility,
                               validate_policy)
from llmwiki.cognitive.session import add_step, complete_session


def _goal(**kw):
    base = dict(goal_id="g1", title="Dominar ES", root="concepts/es.md",
                depth_desired={"conceptual": 2, "technical": 2})
    base.update(kw)
    return new_focus_goal(**base)


def _view(page="concepts/x.md", **kw):
    return KnowledgeItemView(page=page, title=page, **kw)


POLICY = validate_policy({})


# ------------------------------------------------------------ validação
def test_goal_and_policy_validation():
    with pytest.raises(ValueError):
        _goal(depth_desired={"telepatia": 2})
    with pytest.raises(ValueError):
        _goal(priority=9)
    with pytest.raises(ValueError):
        validate_policy({"weights": {"user_focus": -1}})
    with pytest.raises(ValueError):
        validate_policy({"budgets": {"max_conceitos": 3}})
    assert validate_policy({"budgets": {"max_items": 3}})["budgets"][
        "max_items"] == 3
    assert DEFAULT_POLICY["budgets"]["max_items"] == 7   # default inalterado


# ------------------------------------------------------------ hard gates
def test_gates_are_binary_and_named():
    goal = _goal()
    ok, _ = hard_gates(_view(distance=1), goal, POLICY)
    assert ok
    for view, needle in (
            (_view(superseded=True), "superseded"),
            (_view(invalid=True), "invalid"),
            (_view(sensitive=True), "privacy"),
            (_view(distance=9), "scope")):
        ok, refused = hard_gates(view, goal, POLICY)
        assert not ok and any(needle in r for r in refused)
    ok, refused = hard_gates(_view(page="concepts/fora.md"),
                             _goal(excluded=["concepts/fora.md"]), POLICY)
    assert not ok and "excluded" in refused[0]


def test_high_priority_never_beats_privacy_gate():
    """Invariante §18.2: prioridade alta não supera privacy_allowed=false."""
    goal = _goal()
    sensitive = _view(page=goal["root"], sensitive=True, review_due=True,
                      degree=10)                      # tudo puxando p/ cima
    ws = build_working_set([sensitive], goal, POLICY)
    assert ws["items"] == []
    assert any("privacy" in r for e in ws["excluded_by_gate"]
               for r in e["refused"])


def test_superseded_never_enters_working_set():
    goal = _goal()
    ws = build_working_set(
        [_view(page=goal["root"], superseded=True)], goal, POLICY)
    assert ws["items"] == [] and ws["eligible"] == 0


# ------------------------------------------------------------ score
def test_raising_user_focus_never_lowers_priority():
    """Propriedade §18.2: pinned (user_focus máximo) ≥ não-pinned,
    mantidos os demais sinais — em amostra aleatória de views."""
    rng = random.Random(3)
    goal = _goal()
    for _ in range(100):
        kw = dict(distance=rng.randint(0, 2), degree=rng.randint(0, 9),
                  words=rng.randint(50, 3000), heat=rng.random(),
                  review_due=rng.random() < 0.3,
                  accessibility_level=rng.choice(("none", "recall")))
        base = cognitive_priority(_view(**kw), goal, POLICY)
        pinned = cognitive_priority(_view(pinned=True, **kw), goal, POLICY)
        assert pinned.score >= base.score


def test_score_is_decomposed_and_explained():
    goal = _goal()
    scored = cognitive_priority(
        _view(page=goal["root"], review_due=True), goal, POLICY)
    assert set(scored.components) == set(POLICY["weights"])
    assert any("raiz" in r for r in scored.reasons)
    assert any("revisão" in r for r in scored.reasons)


# ------------------------------------------------------------ orçamento
def test_shrinking_budget_never_grows_projection():
    """Propriedade §18.2: reduzir orçamento não aumenta o projetado."""
    rng = random.Random(7)
    goal = _goal()
    candidates = [_view(page=f"concepts/c{i}.md", distance=rng.randint(0, 2),
                        degree=rng.randint(0, 8),
                        words=rng.randint(100, 4000))
                  for i in range(30)]
    big = build_working_set(candidates, goal,
                            validate_policy({"budgets": {"max_items": 10,
                                                         "max_cost_min": 120}}))
    small = build_working_set(candidates, goal,
                              validate_policy({"budgets": {"max_items": 4,
                                                           "max_cost_min": 40}}))
    assert len(small["items"]) <= len(big["items"])
    assert {i["page"] for i in small["items"]} <= \
           {i["page"] for i in big["items"]}
    assert small["trimmed_by_budget"]           # e o corte é explicado


def test_golden_projection_breakdown():
    """Golden: conjunto fixo ⇒ ranking, decomposição e razões estáveis."""
    goal = _goal()
    ws = build_working_set([
        _view(page="concepts/es.md", degree=4, words=600),
        _view(page="concepts/cqrs.md", distance=1, degree=6, words=900,
              review_due=True),
        _view(page="concepts/velho.md", distance=1, superseded=True),
        _view(page="questions/quando-nao-usar.md", type="question",
              distance=1, words=60),
    ], goal, POLICY)
    assert [i["page"] for i in ws["items"]] == \
        ["concepts/es.md", "concepts/cqrs.md"]
    root = ws["items"][0]
    assert root["components"]["user_focus"] == 1.0
    assert root["epistemic"] == {"confidence": "extracted",
                                 "stale": False, "low_yield": False}
    assert ws["open_questions"][0]["page"] == "questions/quando-nao-usar.md"
    assert ws["excluded_by_gate"][0]["page"] == "concepts/velho.md"
    assert ws["policy_version"] == 1 and ws["eligible"] == 3


# --------------------------------------------------- prática e agenda
def test_accessibility_ladder_rises_never_falls():
    state = update_accessibility(None, "recall", "success")
    assert state["level"] == "recall" and state["streak"] == 1
    state = update_accessibility(state, "explain", "success")
    assert state["level"] == "explanation"
    state = update_accessibility(state, "recall", "failure")
    assert state["level"] == "explanation" and state["streak"] == 0
    state = update_accessibility(state, "recall", "success")
    assert state["level"] == "explanation"      # nível menor não rebaixa
    with pytest.raises(ValueError):
        update_accessibility(state, "meditar", "success")


def test_spaced_review_grows_resets_and_flags_overconfidence():
    p = POLICY["review"]
    ok = schedule_review(result="success", confidence_before=0.6,
                         previous_interval_days=2.0, horizon_days=60,
                         review_policy=p)
    assert ok["interval_days"] == pytest.approx(4.4)
    fail = schedule_review(result="failure", confidence_before=0.3,
                           previous_interval_days=8.0, horizon_days=60,
                           review_policy=p)
    assert fail["interval_days"] == 1.0
    over = schedule_review(result="failure", confidence_before=0.9,
                           previous_interval_days=8.0, horizon_days=60,
                           review_policy=p)
    assert over["interval_days"] == 0.5
    assert "sobreconfiança" in over["reason"]
    capped = schedule_review(result="success", confidence_before=0.6,
                             previous_interval_days=30.0, horizon_days=30,
                             review_policy=p)
    assert capped["interval_days"] == 10.0      # teto horizonte/3


# ------------------------------------------------------------ sessão
def _ws():
    goal = _goal()
    return goal, build_working_set(
        [_view(page=goal["root"], words=300),
         _view(page="concepts/cqrs.md", distance=1, words=300),
         _view(page="questions/aberta.md", type="question", distance=1)],
        goal, POLICY)


def test_session_lifecycle_and_capsule_preserves_context():
    """Invariante §18.2: suspensa e retomada mantém objetivo, questões
    abertas e próxima ação."""
    goal, ws = _ws()
    session = new_session(session_id="s1", goal=goal, projection_id="p1",
                          working_set=ws, mode="understand",
                          cognitive_state={"load": 3}, now=100.0)
    add_step(session, kind="decision", now=101.0,
             note="começar pelo raiz")
    add_step(session, kind="read", now=102.0, item="concepts/cqrs.md")
    capsule = suspend_session(session, reason="reunião",
                              next_step="tentar explain do raiz", now=103.0)
    assert session["state"] == "suspended"
    assert capsule["goal_id"] == goal["id"]
    assert capsule["open_questions"] == ["questions/aberta.md"]
    assert capsule["last_decision"] == "começar pelo raiz"
    assert capsule["next_step"] == "tentar explain do raiz"
    assert capsule["policy_version"] == 1
    with pytest.raises(ValueError):              # transições inválidas
        suspend_session(session, reason="x", next_step=None, now=104.0)
    restored = resume_session(session, now=105.0)
    assert session["state"] == "active"
    assert restored["next_step"] == "tentar explain do raiz"
    assert session["open_questions"] == ["questions/aberta.md"]
    complete_session(session, now=106.0)
    with pytest.raises(ValueError):
        resume_session(session, now=107.0)


def test_session_rejects_unknown_mode_and_steps_when_not_active():
    goal, ws = _ws()
    with pytest.raises(ValueError):
        new_session(session_id="s2", goal=goal, projection_id="p1",
                    working_set=ws, mode="hipnose",
                    cognitive_state={}, now=1.0)
    session = new_session(session_id="s3", goal=goal, projection_id="p1",
                          working_set=ws, mode="retain",
                          cognitive_state={}, now=1.0)
    suspend_session(session, reason="", next_step=None, now=2.0)
    with pytest.raises(ValueError):
        add_step(session, kind="read", now=3.0)
