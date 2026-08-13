from __future__ import annotations
from dataclasses import dataclass, field

Confidence = str  # 'extracted' | 'inferred' | 'ambiguous'  (escala única, §1.4)

# prioridade na resolução de sobreposição (maior vence em empate de tamanho)
PRIORITY = {"identifier": 5, "standard": 4, "date": 3, "quantity": 2,
            "geo": 1, "entity": 1}

# classes reescrevíveis em páginas de máquina (§1.2); o resto é só anexo
REWRITE_KINDS = {"entity", "standard", "identifier"}

# identificadores que marcam a página como dado sensível (LGPD topológica)
SENSITIVE_IDS = {"cpf", "cnpj", "iban"}

@dataclass
class Match:
    start: int
    end: int
    kind: str                 # identifier|standard|date|quantity|geo|entity
    subkind: str              # cpf|doi|iso|date|qty|country|stack|publisher|...
    surface: str              # como está no texto
    canonical: str            # forma canônica de exibição
    confidence: Confidence = "extracted"
    data: dict = field(default_factory=dict)   # {"iso": "...", "value": 12.5, ...}
    valid: bool | None = None                  # checksum, quando aplicável

@dataclass
class NormReport:
    matches: list[Match] = field(default_factory=list)
    sensitive: bool = False

    def by_kind(self, kind: str) -> list[Match]:
        return [m for m in self.matches if m.kind == kind]

    def entities_frontmatter(self, limit: int = 12) -> list[str]:
        """Lista curta e legível para o frontmatter (o anexo completo vai ao index.db)."""
        seen: dict[str, int] = {}
        for m in self.matches:
            if m.kind in ("entity", "standard") and m.confidence != "ambiguous":
                seen[m.canonical] = seen.get(m.canonical, 0) + 1
        return [k for k, _ in sorted(seen.items(), key=lambda kv: -kv[1])[:limit]]
