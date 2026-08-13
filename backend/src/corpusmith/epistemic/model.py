"""Tipos fechados do domínio epistêmico — estados inválidos não compilam.

Vocabulários são Enum (não strings livres); agregados são dataclasses
congeladas. NÃO reutiliza o campo `confidence` existente do produto:
`guarantee_kind`/`evaluation_status`/`evidence` são eixos SEPARADOS de
proveniência (extracted/inferred/ambiguous) e de confiança preditiva.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class GuaranteeKind(str, Enum):
    DETERMINISTIC = "deterministic"
    PROPERTY_TESTED = "property_tested"
    EMPIRICAL = "empirical"
    CALIBRATED_EMPIRICAL = "calibrated_empirical"
    PROBABILISTIC = "probabilistic"
    ONLINE_REGRET_RELATIVE = "online_regret_relative"
    HEURISTIC = "heuristic"
    FORMAL = "formal"
    NONE = "none"


# tipos que dispensam "relativo a quê" (a garantia é a própria construção)
SELF_CONTAINED_GUARANTEES = frozenset(
    {GuaranteeKind.DETERMINISTIC, GuaranteeKind.NONE})
# tipos heurísticos/estatísticos: failure modes são OBRIGATÓRIOS
HEURISTIC_GUARANTEES = frozenset(
    {GuaranteeKind.HEURISTIC, GuaranteeKind.EMPIRICAL,
     GuaranteeKind.CALIBRATED_EMPIRICAL, GuaranteeKind.PROBABILISTIC,
     GuaranteeKind.ONLINE_REGRET_RELATIVE})
# tipos empíricos: exigem vínculo com envelope de avaliação
EMPIRICAL_GUARANTEES = frozenset(
    {GuaranteeKind.EMPIRICAL, GuaranteeKind.CALIBRATED_EMPIRICAL})


class DecisionFallback(str, Enum):
    ABSTAIN = "abstain"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    REQUEST_HUMAN_REVIEW = "request_human_review"
    DEGRADE = "degrade"
    DUPLICATE_IN_DOUBT = "duplicate_in_doubt"
    NO_DECISION = "no_decision"


class EvaluationStatus(str, Enum):
    UNEVALUATED = "unevaluated"
    PARTIALLY_EVALUATED = "partially_evaluated"
    EVALUATED = "evaluated"
    DRIFTED = "drifted"
    INVALIDATED = "invalidated"


class EvidenceKind(str, Enum):
    """De onde vem a evidência de QUALIDADE do mecanismo. `self_reported`
    sozinho dispara epistemic.self_certification_only: um mecanismo não
    se valida com uma métrica produzida por ele mesmo."""
    GOLDEN_SET = "golden_set"
    HUMAN_FEEDBACK = "human_feedback"
    DETERMINISTIC_CHECK = "deterministic_check"
    PROPERTY_TEST = "property_test"
    INDEPENDENT_VALIDATOR = "independent_validator"
    SELF_REPORTED = "self_reported"


@dataclass(frozen=True, slots=True)
class InductiveBias:
    text: str


@dataclass(frozen=True, slots=True)
class Assumption:
    text: str


@dataclass(frozen=True, slots=True)
class ValidityScope:
    text: str


@dataclass(frozen=True, slots=True)
class KnownFailureMode:
    text: str


@dataclass(frozen=True, slots=True)
class GuaranteeDescriptor:
    """`universal` MUST ser False — a validação rejeita True (nenhum
    mecanismo do produto tem garantia universal; NFL não é desculpa nem
    impedimento, é o motivo de declarar o escopo)."""
    kind: GuaranteeKind
    relative_to: str = ""
    universal: bool = False


@dataclass(frozen=True, slots=True)
class EpistemicContract:
    mechanism_id: str
    title: str
    decision: str
    implementation_refs: tuple[str, ...]
    inductive_biases: tuple[InductiveBias, ...]
    assumptions: tuple[Assumption, ...]
    validity_scope: tuple[ValidityScope, ...]
    known_failure_modes: tuple[KnownFailureMode, ...]
    guarantee: GuaranteeDescriptor
    fallback: tuple[DecisionFallback, ...] = ()
    adaptive: bool = False
    feedback_signal: str = ""
    composite: bool = False
    composite_components: tuple[str, ...] = ()
    evidence: tuple[EvidenceKind, ...] = ()
    evaluated_by: tuple[str, ...] = ()      # jobs/fluxos que geram envelope
    misinterpretations: tuple[str, ...] = ()
    high_impact: bool = False
    abstention_supported: bool = False
    human_review_available: bool = False
    parameters: tuple[tuple[str, str], ...] = ()   # constantes declaradas

    def to_dict(self) -> dict:
        """Serialização DETERMINÍSTICA (test: serialização estável)."""
        return {
            "mechanism_id": self.mechanism_id,
            "title": self.title,
            "decision": self.decision,
            "implementation_refs": list(self.implementation_refs),
            "inductive_biases": [b.text for b in self.inductive_biases],
            "assumptions": [a.text for a in self.assumptions],
            "validity_scope": [s.text for s in self.validity_scope],
            "known_failure_modes": [m.text for m in self.known_failure_modes],
            "guarantee_kind": self.guarantee.kind.value,
            "guarantee_relative_to": self.guarantee.relative_to,
            "universal_guarantee": self.guarantee.universal,
            "fallback": [f.value for f in self.fallback],
            "adaptive": self.adaptive,
            "feedback_signal": self.feedback_signal,
            "composite": self.composite,
            "composite_components": list(self.composite_components),
            "evidence": [e.value for e in self.evidence],
            "evaluated_by": list(self.evaluated_by),
            "misinterpretations": list(self.misinterpretations),
            "high_impact": self.high_impact,
            "abstention_supported": self.abstention_supported,
            "human_review_available": self.human_review_available,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True, slots=True)
class Registry:
    schema_version: int
    version: str
    contracts: tuple[EpistemicContract, ...] = ()

    def get(self, mechanism_id: str) -> EpistemicContract | None:
        for contract in self.contracts:
            if contract.mechanism_id == mechanism_id:
                return contract
        return None


@dataclass(frozen=True, slots=True)
class Finding:
    """Resultado de validação com CÓDIGO ESTÁVEL (contrato de erro)."""
    code: str
    severity: str            # "error" | "warn"
    mechanism_id: str        # "" = registro inteiro
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "mechanism_id": self.mechanism_id, "message": self.message}


@dataclass(frozen=True, slots=True)
class EvaluationEnvelope:
    """Generalization Envelope — o CONTEXTO exato de uma avaliação: em
    que regime o mecanismo foi medido e, tão importante quanto, onde NÃO
    foi. Uma métrica sem envelope não autoriza generalização."""
    mechanism_id: str
    contract_version: str
    policy_version: str
    product_version: str
    bundle_head: str
    dataset: str
    dataset_sha256: str
    sample_size: int
    query_categories: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    temporal_range: str = ""
    metrics: tuple[tuple[str, float], ...] = ()
    confidence_intervals: tuple[tuple[str, str], ...] = ()
    known_exclusions: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()
    eval_run_ids: tuple[int, ...] = ()
    evaluation_status: EvaluationStatus = EvaluationStatus.UNEVALUATED

    def to_dict(self) -> dict:
        return {
            "mechanism_id": self.mechanism_id,
            "contract_version": self.contract_version,
            "policy_version": self.policy_version,
            "product_version": self.product_version,
            "bundle_head": self.bundle_head,
            "dataset": self.dataset,
            "dataset_sha256": self.dataset_sha256,
            "sample_size": self.sample_size,
            "query_categories": list(self.query_categories),
            "languages": list(self.languages),
            "domains": list(self.domains),
            "temporal_range": self.temporal_range,
            "metrics": dict(self.metrics),
            "confidence_intervals": dict(self.confidence_intervals),
            "known_exclusions": list(self.known_exclusions),
            "out_of_scope": list(self.out_of_scope),
            "eval_run_ids": list(self.eval_run_ids),
            "evaluation_status": self.evaluation_status.value,
        }


def envelope_status(sample_size: int, *, min_sample: int = 20,
                    covered_categories: int = 0,
                    expected_categories: int = 0) -> EvaluationStatus:
    """Regra PURA de status: amostra abaixo do mínimo OU categorias
    faltantes ⇒ partially_evaluated; zero amostra ⇒ unevaluated."""
    if sample_size <= 0:
        return EvaluationStatus.UNEVALUATED
    if sample_size < min_sample:
        return EvaluationStatus.PARTIALLY_EVALUATED
    if expected_categories and covered_categories < expected_categories:
        return EvaluationStatus.PARTIALLY_EVALUATED
    return EvaluationStatus.EVALUATED
