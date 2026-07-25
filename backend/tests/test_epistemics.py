"""v1.6 (ADR-38) — Epistemic Contract Registry + Generalization Envelope.

Cobre: parsing, vocabulários fechados, regras obrigatórias (golden de
findings), determinismo, loader somente-leitura, migração idempotente,
CLI, API via facade, envelopes com hash do golden set e amostra pequena
⇒ partially_evaluated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from llmwiki.api.system import build_app
from llmwiki.epistemic import (EvaluationStatus, RegistryError,
                               envelope_status, parse_registry,
                               validate_registry)
from llmwiki.harness.epistemics import DEFAULT_PATH, lint, load_registry
from llmwiki.runtime.db import SCHEMA_VERSIONS, connect
from llmwiki.runtime.events import EventBus
from llmwiki.runtime.governor import Governor
from llmwiki.runtime.queue import JobQueue

REPO = Path(__file__).resolve().parents[2]

MINIMAL_OK = """
schema_version = 1
[registry]
version = "1.0.0"
[mechanisms.m1]
title = "t"
decision = "d"
implementation_refs = ["backend/pyproject.toml"]
inductive_biases = ["um viés"]
validity_scope = ["um escopo"]
known_failure_modes = ["um modo de falha"]
guarantee_kind = "heuristic"
guarantee_relative_to = "algo observável"
evidence = ["deterministic_check"]
"""


def _findings_codes(text: str, refs: frozenset[str] | None = None):
    registry, parse_findings = parse_registry(text)
    rule_findings = validate_registry(registry, existing_refs=refs)
    return registry, sorted({f.code for f in (*parse_findings,
                                              *rule_findings)})


# ------------------------------------------------------------ parsing
def test_parse_valid_registry_real_file():
    """O epistemics.toml versionado parseia e passa o lint (0 erros)."""
    registry, findings = load_registry()
    assert len(registry.contracts) >= 6
    ids = {c.mechanism_id for c in registry.contracts}
    assert {"retrieval_rrf_hedge", "retrieval_uncertainty", "abstention",
            "reconciliation", "cognitive_priority",
            "metacog_observation_mining"} <= ids
    assert not [f for f in findings if f.severity == "error"]
    assert lint()["ok"] is True


def test_incompatible_schema_version_is_clear_error():
    with pytest.raises(RegistryError, match="schema_version=99"):
        parse_registry("schema_version = 99\n[registry]\nversion='1'")
    with pytest.raises(RegistryError, match="inparseável"):
        parse_registry("isto não é toml = = =")


def test_unknown_fields_are_rejected_not_silently_ignored():
    _, codes = _findings_codes(
        MINIMAL_OK + "campo_inventado = true\n")
    assert "epistemic.unknown_field" in codes


def test_invalid_vocabulary_rejected():
    bad = MINIMAL_OK.replace('guarantee_kind = "heuristic"',
                             'guarantee_kind = "magical"')
    registry, codes = _findings_codes(bad)
    assert "epistemic.invalid_vocabulary" in codes
    assert registry.get("m1") is None      # sem tipo válido não há contrato


# ------------------------------------------------- regras obrigatórias
def test_universal_guarantee_is_forbidden():
    _, codes = _findings_codes(
        MINIMAL_OK + "universal_guarantee = true\n")
    assert "epistemic.guarantee_unbounded" in codes


def test_guarantee_must_declare_relative_to():
    bad = MINIMAL_OK.replace('guarantee_relative_to = "algo observável"',
                             '')
    _, codes = _findings_codes(bad)
    assert "epistemic.guarantee_unbounded" in codes


def test_heuristic_without_failure_modes_is_finding():
    bad = MINIMAL_OK.replace(
        'known_failure_modes = ["um modo de falha"]', '')
    _, codes = _findings_codes(bad)
    assert "epistemic.failure_modes_missing" in codes


def test_empirical_without_evaluation_envelope_is_finding():
    bad = MINIMAL_OK.replace('guarantee_kind = "heuristic"',
                             'guarantee_kind = "empirical"')
    _, codes = _findings_codes(bad)
    assert "epistemic.evaluation_missing" in codes


def test_adaptive_without_feedback_signal_is_finding():
    _, codes = _findings_codes(MINIMAL_OK + "adaptive = true\n")
    assert "epistemic.feedback_signal_missing" in codes


def test_high_impact_without_fallback_is_finding():
    _, codes = _findings_codes(MINIMAL_OK + "high_impact = true\n")
    assert "epistemic.fallback_missing" in codes


def test_composite_without_components_is_finding():
    _, codes = _findings_codes(MINIMAL_OK + "composite = true\n")
    assert "epistemic.components_missing" in codes


def test_missing_implementation_ref_is_finding():
    registry, _ = parse_registry(MINIMAL_OK)
    findings = validate_registry(registry, existing_refs=frozenset())
    assert any(f.code == "epistemic.implementation_ref_missing"
               for f in findings)
    # sem checagem (None) o mesmo contrato passa — o shell decide
    assert not any(f.code == "epistemic.implementation_ref_missing"
                   for f in validate_registry(registry))


def test_self_certification_only_is_finding():
    bad = MINIMAL_OK.replace('evidence = ["deterministic_check"]',
                             'evidence = ["self_reported"]')
    _, codes = _findings_codes(bad)
    assert "epistemic.self_certification_only" in codes


def test_forbidden_justifications():
    """Gödel/No-Free-Lunch não justificam desempenho de ML em contrato."""
    for phrase in ("Gödel garante o limite", "por No Free Lunch nada serve"):
        bad = MINIMAL_OK + f'assumptions = ["{phrase}"]\n'
        _, codes = _findings_codes(bad)
        assert "epistemic.forbidden_justification" in codes, phrase


def test_findings_golden():
    """Golden: um contrato ruim produz EXATAMENTE estes códigos."""
    bad = """
schema_version = 1
[registry]
version = "1.0.0"
[mechanisms.ruim]
title = "sem quase tudo"
decision = "decidir mal"
guarantee_kind = "heuristic"
universal_guarantee = true
adaptive = true
high_impact = true
composite = true
evidence = ["self_reported"]
"""
    registry, parse_findings = parse_registry(bad)
    findings = validate_registry(registry, existing_refs=frozenset())
    got = sorted(f.code for f in (*parse_findings, *findings))
    assert got == [
        "epistemic.components_missing",
        "epistemic.contract_missing_bias",
        "epistemic.contract_missing_scope",
        "epistemic.failure_modes_missing",
        "epistemic.fallback_missing",
        "epistemic.feedback_signal_missing",
        "epistemic.guarantee_unbounded",       # universal=true
        "epistemic.guarantee_unbounded",       # sem relative_to
        "epistemic.implementation_ref_missing",
        "epistemic.self_certification_only",
    ]


# ------------------------------------------------------- determinismo
def test_serialization_is_deterministic():
    registry, _ = parse_registry(MINIMAL_OK)
    again, _ = parse_registry(MINIMAL_OK)
    dump = json.dumps([c.to_dict() for c in registry.contracts],
                      sort_keys=True)
    assert dump == json.dumps([c.to_dict() for c in again.contracts],
                              sort_keys=True)


def test_contract_order_does_not_change_result():
    header = 'schema_version = 1\n[registry]\nversion = "1.0.0"\n'
    body = MINIMAL_OK.split("[mechanisms.m1]")[1]     # campos do contrato
    a = header + "[mechanisms.m1]" + body + "[mechanisms.m2]" + body
    b = header + "[mechanisms.m2]" + body + "[mechanisms.m1]" + body
    ra, fa = parse_registry(a)
    rb, fb = parse_registry(b)
    assert [c.mechanism_id for c in ra.contracts] == \
           [c.mechanism_id for c in rb.contracts] == ["m1", "m2"]
    assert validate_registry(ra) == validate_registry(rb)
    assert fa == fb


def test_loader_never_writes():
    before = hashlib.sha256(DEFAULT_PATH.read_bytes()).hexdigest()
    mtime = DEFAULT_PATH.stat().st_mtime_ns
    load_registry()
    lint()
    assert hashlib.sha256(DEFAULT_PATH.read_bytes()).hexdigest() == before
    assert DEFAULT_PATH.stat().st_mtime_ns == mtime


# ------------------------------------------------ arquitetura/migração
def test_epistemic_domain_is_pure():
    """Redundante com test_architecture (defesa em profundidade): o
    domínio epistêmico não importa infraestrutura nem transporte."""
    import ast
    src = REPO / "backend" / "src" / "llmwiki" / "epistemic"
    forbidden = {"sqlite3", "httpx", "pathlib", "yaml", "pydantic",
                 "fastapi", "requests", "subprocess"}
    for module in src.rglob("*.py"):
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not names & forbidden, f"{module}: {names & forbidden}"


def test_runtime_migration_is_idempotent(settings):
    """Idempotência da migração do runtime.db + presença das tabelas que
    cada versão introduziu. Sem número cravado (era `== 7`): a versão sobe
    a cada fase e o pino fazia o teste falhar por deriva, não por defeito —
    a MESMA classe de problema que o PR-0 atacou no gate."""
    esperada = SCHEMA_VERSIONS["runtime.db"]
    path = settings.app_support / "runtime.db"
    first = connect(path)
    tables = {r["name"] for r in first.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "evaluation_envelopes" in tables      # v1.6 (ADR-38)
    assert "curation_acts" in tables             # v1.8.1 (ADR-41)
    stamped = first.execute("SELECT value FROM _meta WHERE "
                            "key='schema_version'").fetchone()["value"]
    assert int(stamped) == esperada
    first.close()
    second = connect(path)                       # reconexão: sem erro, sem
    again = second.execute("SELECT value FROM _meta WHERE "  # re-migração
                           "key='schema_version'").fetchone()["value"]
    assert int(again) == esperada
    ledger = second.execute("SELECT COUNT(*) c FROM schema_migrations "
                            "WHERE to_version=?", (esperada,)).fetchone()["c"]
    assert ledger == 1
    second.close()


# ------------------------------------------------------------ CLI/API
def test_cli_lint_exit_codes(settings, capsys):
    from llmwiki.cli import cmd_epistemics
    ns = argparse.Namespace(op="lint", mechanism=None)
    assert cmd_epistemics(settings, ns) == 0
    out = capsys.readouterr().out
    assert "mecanismo(s), 0 finding(s)" in out
    # registro quebrado ⇒ ok=False (exit 1 no comando)
    broken = lint(path=settings.home / "nao_existe.toml")
    assert broken["ok"] is False
    assert broken["findings"][0]["code"] == "epistemic.registry_missing"


def test_cli_list_and_show(settings, capsys):
    from llmwiki.cli import cmd_epistemics
    assert cmd_epistemics(settings, argparse.Namespace(
        op="list", mechanism=None)) == 0
    assert "retrieval_rrf_hedge" in capsys.readouterr().out
    assert cmd_epistemics(settings, argparse.Namespace(
        op="show", mechanism="abstention")) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["guarantee_kind"] == "heuristic"
    assert shown["universal_guarantee"] is False
    assert cmd_epistemics(settings, argparse.Namespace(
        op="show", mechanism="nope")) == 2


@pytest.fixture
def client(settings, kb):
    rt = connect(settings.app_support / "runtime.db")
    app = build_app(settings, JobQueue(rt), Governor(settings, rt),
                    EventBus(rt), token="t")
    with TestClient(app) as c:
        c.headers.update({"x-llmwiki-auth": "t"})
        yield c


def test_api_epistemics_via_facade(client):
    """INV-ARCH-004: o endpoint fala com a CurationFacade (asserção
    estrutural em test_architecture); aqui, o contrato do payload."""
    overview = client.get("/cockpit/epistemics").json()
    assert overview["lint"]["ok"] is True
    ids = {m["mechanism_id"] for m in overview["mechanisms"]}
    assert "reconciliation" in ids
    detail = client.get("/cockpit/epistemics/retrieval_uncertainty").json()
    assert detail["misinterpretations"]
    assert client.get("/cockpit/epistemics/nao_existe").status_code == 404
    evals = client.get(
        "/cockpit/epistemics/abstention/evaluations").json()
    assert evals == {"mechanism_id": "abstention", "evaluations": []}


# ----------------------------------------------- Generalization Envelope
def test_envelope_status_rule():
    assert envelope_status(0) is EvaluationStatus.UNEVALUATED
    assert envelope_status(5) is EvaluationStatus.PARTIALLY_EVALUATED
    assert envelope_status(20) is EvaluationStatus.EVALUATED
    assert envelope_status(50, covered_categories=2, expected_categories=5
                           ) is EvaluationStatus.PARTIALLY_EVALUATED


def test_eval_writes_envelopes_with_golden_hash(settings, kb):
    """Integração: eval → envelopes com sha256 do golden, eval_run_ids
    e amostra pequena ⇒ partially_evaluated (não 'evaluated')."""
    from llmwiki.usecases.evaluate_memory import EvaluateMemory, envelopes_for
    gold = kb / "bundle" / "harness"
    gold.mkdir(exist_ok=True)
    text = json.dumps({"q": "resultado do experimento zeta?",
                       "category": "abstain", "expect_abstain": True})
    (gold / "golden_eval.jsonl").write_text(text)
    out = EvaluateMemory(settings).execute()
    assert out["stats"]["abstain"] == [1, 1]
    written = {e["mechanism_id"] for e in out["envelopes"]}
    assert written == {"retrieval_rrf_hedge", "abstention"}
    envs = envelopes_for(settings, "abstention")
    assert len(envs) == 1
    env = envs[0]
    assert env["dataset_sha256"] == hashlib.sha256(
        text.encode()).hexdigest()
    assert env["sample_size"] == 1
    assert env["evaluation_status"] == "partially_evaluated"   # n < 20
    assert env["eval_run_ids"], "envelope deve referenciar eval_runs"
    assert env["query_categories"] == ["abstain"]
    assert env["product_version"]


def test_eval_without_golden_writes_nothing(settings, kb):
    from llmwiki.usecases.evaluate_memory import EvaluateMemory
    assert "skipped" in EvaluateMemory(settings).execute()
    rt = connect(settings.app_support / "runtime.db")
    n = rt.execute("SELECT COUNT(*) c FROM evaluation_envelopes"
                   ).fetchone()["c"]
    rt.close()
    assert n == 0


# ------------------------------------------------- semântica protegida
def test_uncertainty_is_not_exposed_as_truth_probability():
    """O contrato PROÍBE a leitura 'probabilidade de verdade' e o campo
    da resposta continua se chamando `uncertainty` (dispersão)."""
    registry, _ = load_registry()
    contract = registry.get("retrieval_uncertainty")
    text = " ".join(contract.misinterpretations).lower()
    assert "não é probabilidade" in text
    assert "calibração" in text
    assert "concentrada e incorreta" in text
    import inspect
    from llmwiki.usecases import ask_memory
    src = inspect.getsource(ask_memory)
    assert '"uncertainty": fused.uncertainty' in src
    assert "truth_probability" not in src


def test_eig_documented_as_proxy_not_renamed():
    """Dívida registrada: expected_information_gain é proxy heurístico
    (gap × conectividade); o nome externo é preservado por
    compatibilidade e o contrato o declara explicitamente."""
    registry, _ = load_registry()
    contract = registry.get("cognitive_priority")
    assert "expected_information_gain" in contract.composite_components
    joined = " ".join(m.lower() for m in contract.misinterpretations)
    assert "proxy" in joined
