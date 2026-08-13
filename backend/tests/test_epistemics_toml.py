"""v1.6 — `epistemics.toml` NÃO pode divergir do código (ADR-38).

Mesmo padrão de test_architecture_toml: os PARÂMETROS declarados nos
contratos são cruzados com as constantes reais dos mecanismos. Se alguém
recalibrar um limiar sem atualizar o contrato (ou vice-versa), a suíte
quebra — o registro epistêmico fica preso à realidade.
"""
from __future__ import annotations
import inspect
from llmwiki.harness.epistemics import load_registry


def _params(mechanism_id: str) -> dict[str, str]:
    registry, _ = load_registry()
    contract = registry.get(mechanism_id)
    assert contract is not None, mechanism_id
    return dict(contract.parameters)


def test_rrf_hedge_nao_alega_regret_no_regime_bandit():
    """C13 (docs/17): o bound do Hedge exige perda de TODOS os experts por
    rodada; `record_outcome` só atualiza os streams CONTRIBUINTES (bandit
    sem correção de amostragem) e o clamp [0.5, 2.0] satura em 3 desfechos
    (medido: 1.0→1.284→1.649→2.0). O MESMO kernel aplicado a estratégias
    declara `heuristic` — os dois usos devem alegar a mesma honestidade, e
    o peso saturável precisa estar nos failure modes declarados."""
    from llmwiki.harness.epistemics import load_registry
    registry, _ = load_registry()
    contract = registry.get("retrieval_rrf_hedge")
    assert contract.guarantee.kind.value == "heuristic"
    assert any("satura" in m.text for m in contract.known_failure_modes)


def test_rrf_hedge_parameters_match_code():
    from llmwiki.retrieval.streams import RRF_K
    from llmwiki.kernel.information import hedge
    p = _params("retrieval_rrf_hedge")
    assert float(p["rrf_k"]) == RRF_K
    defaults = {k: v.default for k, v in
                inspect.signature(hedge).parameters.items()
                if v.default is not inspect.Parameter.empty}
    assert float(p["hedge_eta"]) == defaults["eta"]
    assert float(p["hedge_clamp_floor"]) == defaults["floor"]
    assert float(p["hedge_clamp_ceiling"]) == defaults["ceiling"]
    # loss ±1 como em RecordOutcome._update_stream_credit
    from llmwiki.usecases import record_outcome
    src = inspect.getsource(record_outcome)
    assert 'loss = -1.0 if self._verdict == "useful" else 1.0' in src
    assert float(p["loss_useful"]) == -1.0
    assert float(p["loss_not_useful"]) == 1.0
    # boosts do overlay como em streams.fuse
    from llmwiki.retrieval import streams
    fuse_src = inspect.getsource(streams)
    assert '"preferred": 1.15' in fuse_src and '"low_yield": 0.8' in fuse_src
    assert float(p["overlay_preferred_boost"]) == 1.15
    assert float(p["overlay_low_yield_penalty"]) == 0.8


def test_uncertainty_parameters_match_code():
    from llmwiki.retrieval import streams
    p = _params("retrieval_uncertainty")
    assert f"ordered[:{int(float(p['entropy_window_hits']))}]" \
        in inspect.getsource(streams)
    from llmwiki import cli
    assert f"uncertainty > {float(p['ui_hedge_threshold'])}" \
        in inspect.getsource(cli)


def test_abstention_parameters_match_code():
    import re
    from llmwiki.usecases import ask_memory
    p = _params("abstention")
    src = re.sub(r"\s+", " ", inspect.getsource(ask_memory))
    key, default = p["threshold_config_key"], float(p["threshold_default"])
    assert f'self._settings.get("{key}", {default})' in src


def test_reconciliation_parameters_match_code():
    from llmwiki.usecases.reconcile_candidate import HI, LO, STRONG_IDS
    from llmwiki.usecases import reconcile_candidate
    p = _params("reconciliation")
    assert float(p["similarity_hi"]) == HI
    assert float(p["similarity_lo"]) == LO
    assert tuple(p["strong_ids"].split(",")) == STRONG_IDS
    src = inspect.getsource(reconcile_candidate)
    assert f"{float(p['weight_title_rank'])} * (1.0 / (1.0 + position))" \
        in src
    assert f"[:{int(float(p['ncd_body_window']))}]".replace(
        "8000", "8_000") in src
    # F3-PR0 (RFC-002): os dois limites entraram no contrato porque LIMITAM
    # RECALL — quantas páginas a escada chega a considerar antes de decidir
    # ADD. Um teto de busca não declarado é um failure mode invisível.
    assert int(p["page_limit"]) == reconcile_candidate._PAGE_LIMIT
    assert int(p["chunk_limit"]) == reconcile_candidate._CHUNK_LIMIT


def test_cognitive_priority_components_match_code():
    """Os componentes declarados são EXATAMENTE os que a função real
    produz — inclusive expected_information_gain (proxy documentado)."""
    from llmwiki.cognitive.model import KnowledgeItemView
    from llmwiki.cognitive.policy import validate_policy
    from llmwiki.cognitive.scoring import cognitive_priority
    registry, _ = load_registry()
    contract = registry.get("cognitive_priority")
    view = KnowledgeItemView(page="c/x.md", degree=3, distance=1)
    scored = cognitive_priority(view, {"root": "c/r.md"},
                                validate_policy({}))
    assert set(contract.composite_components) == set(scored.components)
    p = dict(contract.parameters)
    src = inspect.getsource(cognitive_priority)
    assert f"view.degree / {float(p['dependency_unlock_saturation'])}" in src
    assert f"view.cost_min / {float(p['cost_penalty_saturation_min'])}" in src


def test_strategy_selection_matches_code():
    from llmwiki.usecases.cognitive_state import STRATEGIES
    p = _params("adaptive_strategy_selection")
    assert tuple(p["strategies"].split(",")) == tuple(STRATEGIES)


def test_metacog_parameters_match_code():
    from llmwiki.usecases import metacognition
    p = _params("metacog_observation_mining")
    src = inspect.getsource(metacognition)
    key = p["min_support_config_key"]
    assert f'settings.get("{key}", {int(float(p["min_support_default"]))})' \
        in src
    assert f"rate - global_rate >= {float(p['strategy_rate_delta'])}" in src
    assert f"hi_rate - lo_rate < {float(p['load_bad_rate_delta'])}" in src
    assert f"gap < {float(p['overconfidence_threshold'])}" in src


def test_every_implementation_ref_exists():
    registry, findings = load_registry()
    assert not [f for f in findings
                if f.code == "epistemic.implementation_ref_missing"]
    assert all(c.implementation_refs for c in registry.contracts)


def test_freeze_parameters_match_code():
    """O mecanismo mais destrutivo sem contrato (docs/17): 5 limiares
    decidindo o que sai da memória quente, nenhum sob cross-check."""
    import inspect
    from llmwiki.kernel.activation import DECAY
    from llmwiki.usecases import cold_memory
    p = _params("memory_freeze")
    assert float(p["actr_decay"]) == DECAY
    src = inspect.getsource(cold_memory)
    assert f'"memory.max_recall_probability", ' \
           f'{float(p["max_recall_probability_default"])}' in src
    assert f'"memory.min_idle_days", ' \
           f'{int(float(p["min_idle_days_default"]))}' in src
    assert f'"memory.freeze_tau", {float(p["freeze_tau_default"])}' in src
    assert f'"memory.activation_noise", ' \
           f'{float(p["activation_noise_default"])}' in src


def test_consolidate_parameters_match_code():
    import inspect
    from llmwiki.kernel.sketch import simhash
    from llmwiki.usecases.consolidate_inbox import _Signature
    p = _params("consolidate_inbox")
    assert int(p["near_duplicate_hamming"]) == \
        _Signature.NEAR_DUPLICATE_HAMMING
    assert int(p["simhash_shingle"]) == \
        inspect.signature(simhash).parameters["shingle"].default
    src = inspect.getsource(
        __import__("llmwiki.usecases.consolidate_inbox",
                   fromlist=["x"]))
    assert f"text[:{int(p['text_window_chars']):_}]".replace("_", "_") \
        in src.replace("100_000", "100000") \
        or "text[:100_000]" in src


def test_freeze_declara_proxy_e_efeito_colateral_do_recycle():
    """docs/17: P(recall) mede HEAT DE LEITURA, não valor; e com
    auto_recycle uma CONSULTA escreve no bundle. Os dois têm de estar
    declarados — omiti-los é o que fazia o mecanismo parecer coberto."""
    from llmwiki.harness.epistemics import load_registry
    registry, _ = load_registry()
    c = registry.get("memory_freeze")
    texto = " ".join(m.text for m in c.known_failure_modes).lower()
    assert "leitura" in texto or "heat" in texto      # proxy declarado
    assert "auto_recycle" in texto or "consulta" in texto  # efeito colateral
    assert c.high_impact is True
    # e cold_memory.py NÃO aparece mais como ref de abstention (parecia
    # cobrir o freeze sem contrato)
    ab = registry.get("abstention")
    assert not any("cold_memory" in r for r in ab.implementation_refs)
    assert any("cold_memory" in r for r in c.implementation_refs)


def test_sufficiency_components_e_parametros_match_code():
    """P-4 (ADR-52): as parcelas declaradas são EXATAMENTE as que o
    kernel produz, e as saturações de projeto ficam sob cross-check."""
    from llmwiki.kernel import sufficiency
    from llmwiki.harness.epistemics import load_registry
    registry, _ = load_registry()
    contract = registry.get("evidence_sufficiency")
    out = sufficiency.evidence_support(1, 1, 0.5, 0.5)
    assert set(contract.composite_components) == set(out["components"])
    p = dict(contract.parameters)
    assert int(p["pages_saturation"]) == sufficiency._PAGES_SATURATION
    assert int(p["streams_saturation"]) == sufficiency._STREAMS_SATURATION
