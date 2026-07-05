"""Kernel puro (v0.9): teoria da informação e topologia."""
from __future__ import annotations
from llmwiki.kernel.information import hedge, ncd, shannon_entropy, surprisal
from llmwiki.kernel.topology import component_persistence, fragile_bridges


# ------------------------------------------------------------- informação
def test_entropy_bounds():
    assert shannon_entropy([1.0]) == 0.0                    # certeza
    assert abs(shannon_entropy([1, 1, 1, 1]) - 1.0) < 1e-9  # uniforme
    peaked = shannon_entropy([100, 1, 1, 1])
    spread = shannon_entropy([10, 9, 8, 7])
    assert peaked < spread                                   # massa concentrada


def test_ncd_similar_vs_distinct():
    a = "o reranker bge foi adotado para as consultas profundas " * 20
    b = "o reranker bge foi escolhido para consultas profundas " * 20
    c = "receita de bolo de cenoura com cobertura de chocolate " * 20
    assert ncd(a, a) < 0.15                     # auto-similaridade ~0
    assert ncd(a, b) < ncd(a, c)                # paráfrase < tema distinto
    assert ncd(a, c) > 0.5


def test_surprisal_rare_entity_carries_more_information():
    assert surprisal(1, 1000) > surprisal(500, 1000) > surprisal(1000, 1000)
    assert surprisal(1000, 1000) == 0.0         # onipresente informa 0 bits


def test_hedge_rewards_and_clamps():
    weights = {"fts": 1.0, "entity": 1.0}
    after = hedge(weights, {"fts": 1.0})        # fts levou a um beco
    assert after["fts"] < 1.0 and after["entity"] == 1.0
    after = hedge(after, {"fts": -1.0})         # depois acertou
    assert after["fts"] > hedge(weights, {"fts": 1.0})["fts"]
    floored = weights
    for _ in range(50):                          # nunca silencia um stream
        floored = hedge(floored, {"fts": 1.0})
    assert floored["fts"] == 0.5
    ceiled = weights
    for _ in range(50):
        ceiled = hedge(ceiled, {"fts": -1.0})
    assert ceiled["fts"] == 2.0


# --------------------------------------------------------------- topologia
def _two_blocks_with_weak_bridge():
    strong = [("a1", "a2", 3.0), ("a2", "a3", 3.0), ("a1", "a3", 3.0),
              ("b1", "b2", 3.0), ("b2", "b3", 3.0), ("b1", "b3", 3.0)]
    return strong + [("a1", "b1", 0.2)]          # o fio fraco


def test_persistence_finds_the_fragile_bridge():
    bridges = fragile_bridges(_two_blocks_with_weak_bridge())
    assert len(bridges) == 1
    bridge = bridges[0]
    assert {bridge.src, bridge.dst} == {"a1", "b1"}
    assert bridge.weight == 0.2
    assert bridge.small_side == 3 and bridge.large_side == 3


def test_intra_block_merges_are_not_bridges():
    events = component_persistence(_two_blocks_with_weak_bridge())
    # 6 nós ⇒ 6 fusões até virar 1 componente (árvore geradora + extras skip)
    intra = [e for e in events if not e.is_bridge]
    assert all(e.small_side == 1 for e in intra)  # fusões folha-a-bloco
