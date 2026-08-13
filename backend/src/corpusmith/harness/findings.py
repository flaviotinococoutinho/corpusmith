from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, Iterator


@dataclass
class Finding:
    severity: str                     # "error" | "warn" | "info"
    rule: str                         # ex.: "okf.broken_link", "policy.privacy_required"
    path: str                         # rel_path da página (ou arquivo reservado)
    message: str
    okf_conformance: bool = False     # True = camada SPEC; False = política local
    meta: dict = field(default_factory=dict)


class Findings:
    """Coleção de primeira classe (Object Calisthenics): a lista de findings
    com o vocabulário do domínio em vez de list[Finding] nua — quem consome
    pergunta `has_errors()`/`rules()` em vez de reimplementar filtros."""

    def __init__(self, items: Iterable[Finding] = ()):
        self._items: list[Finding] = list(items)

    def add(self, finding: Finding) -> None:
        self._items.append(finding)

    def extend(self, more: Iterable[Finding]) -> "Findings":
        self._items.extend(more)
        return self

    def errors(self) -> "Findings":
        return Findings(f for f in self._items if f.severity == "error")

    def has_errors(self) -> bool:
        return any(f.severity == "error" for f in self._items)

    def rules(self) -> set[str]:
        return {f.rule for f in self._items}

    def count(self, severity: str) -> int:
        return sum(f.severity == severity for f in self._items)

    def to_dicts(self) -> list[dict]:
        return [f.__dict__ for f in self._items]

    def __iter__(self) -> Iterator[Finding]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)
