"""Loader do registro epistêmico (shell) — a ÚNICA implementação de
carga/validação, compartilhada por CLI, facade, API e testes (ADR-38).

Lê epistemics.toml (raiz do repo, override por caminho explícito), delega
parsing e regras ao domínio PURO (epistemic/) e acrescenta a única
checagem que exige filesystem: existência dos implementation_refs.
Somente leitura — o loader jamais escreve (propriedade testada).
"""
from __future__ import annotations
from pathlib import Path
from ..epistemic import (Finding, Registry, RegistryError, parse_registry,
                         validate_registry)
from ..paths import frozen, resource as _resource

# harness/ → llmwiki → src → backend → raiz do repo
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATH = _resource("epistemics.toml", source_root=_REPO_ROOT)


def load_registry(path: Path | str | None = None
                  ) -> tuple[Registry, tuple[Finding, ...]]:
    """Registro + findings (parsing ∪ regras ∪ refs inexistentes),
    ordenados deterministicamente. RegistryError se inparseável ou de
    versão incompatível; FileNotFoundError se o arquivo não existir."""
    toml_path = Path(path) if path else DEFAULT_PATH
    registry, parse_findings = parse_registry(toml_path.read_text())
    referenced = {ref for contract in registry.contracts
                  for ref in contract.implementation_refs}
    if frozen():
        # Binário empacotado não carrega a árvore de código: `is_file()` diria
        # "não existe" para TODOS os refs e o painel do app instalado acusaria
        # ~15 erros que não existem. A checagem é de desenvolvimento/CI; aqui
        # ela não é respondível — e dizer isso é diferente de omitir.
        existing = frozenset(referenced)
    else:
        existing = frozenset(ref for ref in referenced
                             if (_REPO_ROOT / ref).is_file())
    rule_findings = validate_registry(registry, existing_refs=existing)
    merged = sorted(set(parse_findings) | set(rule_findings),
                    key=lambda f: (f.mechanism_id, f.code, f.message))
    return registry, tuple(merged)


# G-10 (auditoria `docs/17`): `validate_registry` itera contrato a contrato e
# não existe nenhuma regra sobre o CONJUNTO. Provado por mutação: apagar as 45
# linhas de `[mechanisms.theme_identity_matching]` deixa o lint responder
# "14 mecanismo(s), 0 finding(s)", exit 0, suíte inteira verde. O registro é a
# fonte normativa do que o produto AFIRMA saber — perder um contrato em silêncio
# é o modo de falha mais caro que ele tem.
#
# Duas listas, porque são dois erros diferentes e uma severidade só misturaria
# ruído com defeito:
#
# - `EXPECTED_MECHANISMS` — os que ESTÃO no registro hoje. Sumiço é **error**:
#   remover um contrato passa a exigir remover o nome aqui, no mesmo commit, o
#   que torna a remoção uma decisão registrada em vez de um esquecimento;
# - `PROMISED_MECHANISMS` — os que `docs/14` §5 declara obrigatórios e que
#   ainda não existem. **warn**, não error: o produto não os tem porque as fases
#   que os entregam não rodaram. Fazê-los vermelhos hoje só produziria dois
#   desfechos ruins — contrato escrito às pressas para calar o gate, ou o gate
#   desligado. Warn mantém a dívida VISÍVEL no mesmo lugar onde ela será paga.
EXPECTED_MECHANISMS = (
    "abstention", "adaptive_strategy_selection", "cognitive_priority",
    "graph_cache", "metacog_observation_mining", "native_graph_kernel",
    "native_index_builder", "native_sketch_kernel", "native_text_extraction",
    "pattern_layer_snapshot", "reconciliation", "retrieval_rrf_hedge",
    "retrieval_uncertainty", "theme_identity_matching", "worker_isolation",
)

# `docs/14` §5: "quatro contratos novos obrigatórios" seguido de SEIS nomes —
# `pattern_layer_snapshot` já entrou (F2), os cinco abaixo não.
PROMISED_MECHANISMS = (
    ("attention_queue", "docs/14 §4 (fila de atenção)"),
    ("evidence_sufficiency", "docs/14 §4 (selo 2D de suporte)"),
    ("factual_conflict", "docs/14 §4 (policy.factual_conflict)"),
    ("inferred_cooccurrence_edges", "docs/14 §4 (co-menção materializada)"),
    ("temporal_partition", "docs/14 §5"),
)


def _completude(registry: Registry) -> list[Finding]:
    """Findings sobre o CONJUNTO de mecanismos, não sobre cada um (G-10)."""
    presentes = {c.mechanism_id for c in registry.contracts}
    achados = [
        Finding(code="epistemic.mechanism_missing", severity="error",
                mechanism_id=m,
                message="mecanismo esperado e AUSENTE do registro — se a "
                        "remoção foi intencional, tire de "
                        "EXPECTED_MECHANISMS no mesmo commit")
        for m in EXPECTED_MECHANISMS if m not in presentes
    ]
    achados += [
        Finding(code="epistemic.mechanism_promised", severity="warn",
                mechanism_id=m,
                message=f"contrato declarado obrigatório em {onde} e ainda "
                        f"não escrito — dívida conhecida, não regressão")
        for m, onde in PROMISED_MECHANISMS if m not in presentes
    ]
    if frozen():
        achados.append(Finding(
            code="epistemic.refs_uncheckable", severity="warn",
            mechanism_id="",
            message="binário empacotado: a existência dos implementation_refs "
                    "não foi verificada (a árvore de código não é embarcada) "
                    "— essa checagem vale no repositório e na CI"))
    return achados


def lint(path: Path | str | None = None) -> dict:
    """Resultado estruturado para CLI/API/painel — a MESMA fonte."""
    try:
        registry, findings = load_registry(path)
    except FileNotFoundError:
        return {"ok": False, "registry_version": None, "mechanisms": 0,
                "findings": [{"code": "epistemic.registry_missing",
                              "severity": "error", "mechanism_id": "",
                              "message": "epistemics.toml não encontrado"}]}
    except RegistryError as e:
        return {"ok": False, "registry_version": None, "mechanisms": 0,
                "findings": [{"code": "epistemic.registry_unreadable",
                              "severity": "error", "mechanism_id": "",
                              "message": str(e)}]}
    findings = list(findings) + _completude(registry)
    errors = sum(1 for f in findings if f.severity == "error")
    return {"ok": errors == 0,
            "registry_version": registry.version,
            "mechanisms": len(registry.contracts),
            "findings": [f.to_dict() for f in findings]}
