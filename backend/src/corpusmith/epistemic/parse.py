"""Texto TOML → Registry (PURO: string entra, tipos saem — zero I/O).

Estrito onde silêncio esconderia erro: campo desconhecido e vocabulário
inválido viram FINDING de erro (não crash — o lint reporta tudo de uma
vez); só o inparseável de verdade (TOML inválido, schema_version errado)
levanta RegistryError com mensagem clara.
"""
from __future__ import annotations
import re
import tomllib
from .model import (Assumption, DecisionFallback, EpistemicContract,
                    EvidenceKind, Finding, GuaranteeDescriptor,
                    GuaranteeKind, InductiveBias, KnownFailureMode,
                    Registry, SideEffect, ValidityScope)

SUPPORTED_SCHEMA = 1
_SEMVER = re.compile(r"\d+\.\d+\.\d+")

_KNOWN_FIELDS = {
    "title", "decision", "implementation_refs", "inductive_biases",
    "assumptions", "validity_scope", "known_failure_modes",
    "guarantee_kind", "guarantee_relative_to", "universal_guarantee",
    "fallback", "adaptive", "feedback_signal", "composite",
    "composite_components", "evidence", "side_effects", "evaluated_by",
    "misinterpretations", "high_impact", "abstention_supported",
    "human_review_available", "parameters",
}


class RegistryError(ValueError):
    """Registro inparseável ou de versão incompatível — mensagem clara."""


def _strings(raw: dict, key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    return tuple(str(v) for v in value) if isinstance(value, list) else ()


def _enum(kind, value: str, mechanism: str, field: str,
          findings: list[Finding]):
    try:
        return kind(value)
    except ValueError:
        allowed = ", ".join(e.value for e in kind)
        findings.append(Finding(
            "epistemic.invalid_vocabulary", "error", mechanism,
            f"{field}='{value}' fora do vocabulário fechado ({allowed})"))
        return None


def _contract(mechanism_id: str, raw: dict,
              findings: list[Finding]) -> EpistemicContract | None:
    unknown = set(raw) - _KNOWN_FIELDS
    for key in sorted(unknown):
        findings.append(Finding(
            "epistemic.unknown_field", "error", mechanism_id,
            f"campo desconhecido '{key}' — rejeitado para evitar erro "
            f"silencioso (typo? ou registro escrito por versão mais nova "
            f"do produto: campo OPCIONAL com default seguro não bumpa "
            f"`schema_version`, porque bumpar quebraria a direção que "
            f"importa — código novo lendo registro antigo)"))
    kind = _enum(GuaranteeKind, str(raw.get("guarantee_kind", "none")),
                 mechanism_id, "guarantee_kind", findings)
    fallbacks, evidence = [], []
    for value in _strings(raw, "fallback"):
        parsed = _enum(DecisionFallback, value, mechanism_id, "fallback",
                       findings)
        if parsed:
            fallbacks.append(parsed)
    side_effects = []
    for value in _strings(raw, "side_effects"):
        parsed = _enum(SideEffect, value, mechanism_id, "side_effects",
                       findings)
        if parsed:
            side_effects.append(parsed)
    for value in _strings(raw, "evidence"):
        parsed = _enum(EvidenceKind, value, mechanism_id, "evidence",
                       findings)
        if parsed:
            evidence.append(parsed)
    if kind is None:
        return None                      # sem tipo de garantia não há contrato
    parameters = raw.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}
    return EpistemicContract(
        mechanism_id=mechanism_id,
        title=str(raw.get("title", "")),
        decision=str(raw.get("decision", "")),
        implementation_refs=_strings(raw, "implementation_refs"),
        inductive_biases=tuple(InductiveBias(t) for t in
                               _strings(raw, "inductive_biases")),
        assumptions=tuple(Assumption(t) for t in
                          _strings(raw, "assumptions")),
        validity_scope=tuple(ValidityScope(t) for t in
                             _strings(raw, "validity_scope")),
        known_failure_modes=tuple(KnownFailureMode(t) for t in
                                  _strings(raw, "known_failure_modes")),
        guarantee=GuaranteeDescriptor(
            kind=kind,
            relative_to=str(raw.get("guarantee_relative_to", "")),
            universal=bool(raw.get("universal_guarantee", False))),
        fallback=tuple(fallbacks),
        adaptive=bool(raw.get("adaptive", False)),
        feedback_signal=str(raw.get("feedback_signal", "")),
        composite=bool(raw.get("composite", False)),
        composite_components=_strings(raw, "composite_components"),
        evidence=tuple(evidence),
        side_effects=tuple(side_effects),
        evaluated_by=_strings(raw, "evaluated_by"),
        misinterpretations=_strings(raw, "misinterpretations"),
        high_impact=bool(raw.get("high_impact", False)),
        abstention_supported=bool(raw.get("abstention_supported", False)),
        human_review_available=bool(raw.get("human_review_available",
                                            False)),
        parameters=tuple(sorted((str(k), str(v))
                                for k, v in parameters.items())))


def parse_registry(text: str) -> tuple[Registry, tuple[Finding, ...]]:
    """Devolve (registro, findings de parsing). Ordem dos mecanismos no
    arquivo NÃO altera o resultado: contratos e findings saem ordenados."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise RegistryError(f"epistemics.toml inparseável: {e}") from e
    schema = data.get("schema_version")
    if schema != SUPPORTED_SCHEMA:
        raise RegistryError(
            f"schema_version={schema!r} incompatível — este produto "
            f"suporta {SUPPORTED_SCHEMA}; atualize o corpusmith ou o arquivo")
    registry_meta = data.get("registry")
    if not isinstance(registry_meta, dict) or "version" not in registry_meta:
        raise RegistryError("[registry].version ausente")
    # G-10: `version = "banana"` passava. A version é o que quatro PRs
    # prometem bumpar; um valor que não ordena não distingue registro novo de
    # registro velho, e o "1.1.0 → 1.2.0" do plano vira decoração.
    if not _SEMVER.fullmatch(str(registry_meta["version"])):
        raise RegistryError(
            f"[registry].version={registry_meta['version']!r} não é semver "
            f"MAJOR.MINOR.PATCH — uma version que não ordena não consegue "
            f"dizer que um registro é mais novo que outro")
    mechanisms = data.get("mechanisms", {})
    if not isinstance(mechanisms, dict):
        raise RegistryError("[mechanisms] deve ser uma tabela")
    top_unknown = set(data) - {"schema_version", "registry", "mechanisms"}
    findings: list[Finding] = [
        Finding("epistemic.unknown_field", "error", "",
                f"chave de topo desconhecida '{key}'")
        for key in sorted(top_unknown)]
    contracts = []
    for mechanism_id in sorted(mechanisms):
        raw = mechanisms[mechanism_id]
        if not isinstance(raw, dict):
            findings.append(Finding(
                "epistemic.unknown_field", "error", mechanism_id,
                "mecanismo deve ser uma tabela TOML"))
            continue
        contract = _contract(mechanism_id, raw, findings)
        if contract:
            contracts.append(contract)
    findings.sort(key=lambda f: (f.mechanism_id, f.code, f.message))
    return (Registry(schema_version=schema,
                     version=str(registry_meta["version"]),
                     contracts=tuple(contracts)),
            tuple(findings))
