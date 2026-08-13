"""v0.21 — triagem do mapa interdisciplinar: VoI no score, scaffolding
com fading, intercalação, Toulmin na crítica, tipos epistemológicos e
memória episódica da experiência."""
from __future__ import annotations
import pytest
from corpusmith.cognitive import KnowledgeItemView, validate_policy
from corpusmith.cognitive.progress import (exercise_prompt, interleave,
                                        support_level)
from corpusmith.cognitive.scoring import cognitive_priority
from corpusmith.cognitive.model import new_focus_goal


def _goal():
    return new_focus_goal(goal_id="g", title="t", root="concepts/r.md",
                          depth_desired={"conceptual": 2})


def test_value_of_information_is_gap_times_unlock_and_separate():
    policy = validate_policy({})
    assert "expected_information_gain" in policy["weights"]
    connective = cognitive_priority(
        KnowledgeItemView(page="concepts/hub.md", distance=1, degree=8),
        _goal(), policy)
    leaf = cognitive_priority(
        KnowledgeItemView(page="concepts/folha.md", distance=1, degree=0),
        _goal(), policy)
    assert connective.components["expected_information_gain"] > \
        leaf.components["expected_information_gain"]
    assert leaf.components["expected_information_gain"] == 0.0
    assert any("valor de informação" in r for r in connective.reasons)
    # separado de interesse pessoal: user_focus igual nos dois
    assert connective.components["user_focus"] == \
        leaf.components["user_focus"]


def test_scaffolding_fades_with_streak():
    assert support_level(0)["level"] == "worked_example"
    assert support_level(1)["level"] == "hint"
    assert support_level(2)["level"] == "none"
    assert support_level(9)["level"] == "none"


def test_interleave_alternates_groups_stably():
    items = [{"item": "concepts/a1"}, {"item": "concepts/a2"},
             {"item": "questions/q1"}, {"item": "concepts/a3"},
             {"item": "runbooks/r1"}]
    mixed = interleave(items, "item")
    assert [i["item"] for i in mixed] == [
        "concepts/a1", "questions/q1", "runbooks/r1",
        "concepts/a2", "concepts/a3"]        # round-robin, ordem interna


def test_critique_prompt_decomposes_toulmin():
    prompt = exercise_prompt("critique", "CQRS")
    for part in ("AFIRMAÇÃO", "EVIDÊNCIA", "GARANTIA", "RÉPLICA"):
        assert part in prompt


def test_epistemic_types_are_first_class():
    from corpusmith.harness.local_policy import RECOMMENDED_TYPES
    assert {"fact", "claim", "hypothesis", "observation",
            "opinion"} <= RECOMMENDED_TYPES
