"""Domínio PURO dos contratos epistemológicos (v1.6, ADR-38).

Torna explícitos, legíveis por máquina e testáveis os pressupostos dos
mecanismos heurísticos/adaptativos: que decisão cada um toma, sob quais
vieses indutivos, com que garantia RELATIVA, onde foi (e não foi)
avaliado, e quando abster/degradar/pedir revisão humana.

Camadas: `model` (tipos fechados) · `parse` (texto TOML → registro, sem
I/O) · `validate` (regras → findings determinísticos). A leitura de
arquivo vive em harness/epistemics.py (shell); aqui é stdlib pura.
"""
from .model import (Assumption, DecisionFallback, EpistemicContract,
                    EvaluationEnvelope, EvaluationStatus, EvidenceKind,
                    Finding, GuaranteeDescriptor, GuaranteeKind,
                    InductiveBias, KnownFailureMode, Registry,
                    ValidityScope, envelope_status)
from .parse import RegistryError, parse_registry
from .validate import validate_registry

__all__ = [
    "Assumption", "DecisionFallback", "EpistemicContract",
    "EvaluationEnvelope", "EvaluationStatus", "EvidenceKind", "Finding",
    "GuaranteeDescriptor", "GuaranteeKind", "InductiveBias",
    "KnownFailureMode", "Registry", "RegistryError", "ValidityScope",
    "envelope_status", "parse_registry", "validate_registry",
]
