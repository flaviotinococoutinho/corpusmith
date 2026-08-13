"""QA-1 (P1 do backlog v1.3): golden_eval.jsonl distribuído pelo seed —
o eval deixa de ser no-op out-of-the-box — e métricas FRACIONÁRIAS
(recall@5 e MRR por caso, médias no envelope), não só passa/não-passa.

Idempotência: o seed nunca sobrescreve golden nem páginas do usuário."""
from __future__ import annotations
import json
import pytest
from corpusmith.okf.bundle import BundleReader
from corpusmith.okf.git_store import GitStore
from corpusmith.harness.runner import HarnessRunner
from corpusmith.usecases.evaluate_memory import EvaluateMemory
from corpusmith.usecases.seed_eval import seed_golden_eval


def _golden(kb):
    return kb / "bundle" / "harness" / "golden_eval.jsonl"


def test_seed_distribui_golden_com_10_casos_e_categorias(settings, kb):
    out = seed_golden_eval(settings)
    assert out["pages"] >= 5 and out["cases"] >= 10
    cases = [json.loads(l) for l in
             _golden(kb).read_text().splitlines() if l.strip()]
    assert len(cases) >= 10
    categories = {c["category"] for c in cases}
    assert {"temporal", "update", "abstain"} <= categories   # aceite QA-1


def test_paginas_seedadas_passam_no_harness(settings, kb):
    seed_golden_eval(settings)
    runner = HarnessRunner(BundleReader(kb / "bundle"), GitStore(kb))
    findings = runner.lint_bundle(kb / "bundle")
    assert not HarnessRunner.has_errors(findings)


def test_seed_e_idempotente_e_nao_sobrescreve_usuario(settings, kb):
    seed_golden_eval(settings)
    custom = '{"q": "minha pergunta", "category": "extract"}\n'
    _golden(kb).write_text(custom)                 # golden CURADO pelo usuário
    out2 = seed_golden_eval(settings)
    assert out2["pages"] == 0 and out2["cases"] == 0
    assert _golden(kb).read_text() == custom       # intacto


def test_eval_roda_out_of_the_box_e_passa(settings, kb):
    seed_golden_eval(settings)
    result = EvaluateMemory(settings).execute()
    assert "skipped" not in result
    stats = result["stats"]
    assert {"temporal", "update", "abstain"} <= set(stats)
    total = sum(t for t, _ in stats.values())
    passed = sum(p for _, p in stats.values())
    assert total >= 10 and passed == total         # golden é VERDADE local


def test_envelope_nao_inverte_o_escopo_de_validade(settings, kb):
    """B4 do docs/18: `out_of_scope` recebia o `validity_scope` do
    contrato SEM negação — o painel Qualidade dizia que o regime em que o
    mecanismo VALE estava "fora de escopo". O conteúdo honesto do campo
    ("onde NÃO foi medido") são os failure modes declarados."""
    from corpusmith.harness.epistemics import load_registry
    from corpusmith.usecases.evaluate_memory import EvaluateMemory, envelopes_for
    seed_golden_eval(settings)
    EvaluateMemory(settings).execute()
    registry, _ = load_registry()
    contract = next(c for c in registry.contracts
                    if "eval_memory" in c.evaluated_by
                    and c.validity_scope and c.known_failure_modes)
    env = envelopes_for(settings, contract.mechanism_id, limit=1)[0]
    assert env["out_of_scope"] == [m.text for m in
                                   contract.known_failure_modes]
    assert env["out_of_scope"] != [s.text for s in contract.validity_scope]


def test_metricas_fracionarias_recall_e_mrr(settings, kb):
    seed_golden_eval(settings)
    result = EvaluateMemory(settings).execute()
    metrics = result["metrics"]
    assert 0.0 < metrics["mean_recall_at_5"] <= 1.0
    assert 0.0 < metrics["mean_mrr"] <= 1.0
    assert metrics["graded_cases"] >= 5            # casos com expect_pages
