from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Finding:
    severity: str                     # "error" | "warn" | "info"
    rule: str                         # ex.: "okf.broken_link", "policy.privacy_required"
    path: str                         # rel_path da página (ou arquivo reservado)
    message: str
    okf_conformance: bool = False     # True = camada SPEC; False = política local
    meta: dict = field(default_factory=dict)
