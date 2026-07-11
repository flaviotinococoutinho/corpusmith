"""Modelo do domínio cognitivo — vocabulários fechados e views imutáveis.

Separação de estados (ADR-20): NUNCA comprimir em um só campo.
- estado EPISTEMOLÓGICO (da memória): confidence/superseded/stale/…
  chega aqui DENTRO do KnowledgeItemView e é somente-leitura;
- estado de ACESSIBILIDADE cognitiva: a escada ACCESS_LEVELS — o que a
  pessoa consegue FAZER com o item (reconhecer → criticar). Falhar numa
  recuperação mexe aqui, jamais na confiança epistemológica (ACT-R:
  recência/frequência são sinais de acesso, não de verdade);
- estado COGNITIVO atual (declarado) e estado da EXPERIÊNCIA (sessão)
  têm entidades próprias.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# escada de acessibilidade (Bloom-adjacente, ordenada do reconhecer ao
# criticar); o índice é a "profundidade validada" de um item
ACCESS_LEVELS = ("none", "recognition", "recall", "explanation",
                 "application", "transfer", "critique")

# exercício de recuperação ativa → nível que ele valida quando bem-sucedido
EXERCISE_LEVEL = {"recall": "recall", "explain": "explanation",
                  "apply": "application", "compare": "application",
                  "transfer": "transfer", "critique": "critique"}

EXPERIENCE_MODES = ("understand", "apply", "retain", "critique",
                    "transfer", "resume")

# profundidade multidimensional (0..3 por dimensão) — nunca um número só
DEPTH_DIMENSIONS = ("conceptual", "technical", "mathematical",
                    "practical", "historical", "critical", "transfer")

GOAL_INTENTS = ("understand", "apply", "teach", "decide", "research",
                "review")

FEEDBACK_VERDICTS = ("useful", "irrelevant", "too_shallow", "too_deep",
                     "incorrect", "confusing", "redundant", "good_analogy",
                     "missing_example", "missing_formalism", "expand",
                     "postpone", "hide", "resume_later")
FEEDBACK_SCOPES = ("answer", "concept", "relation", "evidence", "analogy",
                   "depth", "strategy", "sequence", "session")

ATTEMPT_RESULTS = ("success", "partial", "failure")


def level_index(level: str) -> int:
    return ACCESS_LEVELS.index(level) if level in ACCESS_LEVELS else 0


@dataclass(frozen=True)
class KnowledgeItemView:
    """A memória VISTA pelo plano cognitivo — DTO imutável montado pelos
    adapters. Campos epistemológicos/estruturais são retrato, não posse:
    nada aqui escreve de volta no canônico."""
    page: str
    title: str = ""
    type: str = "concept"
    # --- estado epistemológico (somente-leitura) ---
    epistemic_confidence: str = "extracted"   # extracted|inferred|ambiguous|human
    superseded: bool = False
    invalid: bool = False                     # bi-temporal: invalid_at no passado
    stale: bool = False
    contested: bool = False
    sensitive: bool = False
    # --- estrutura/custo (peso estrutural e operacional) ---
    distance: int = 0                         # saltos até o conceito raiz
    degree: int = 0
    words: int = 0
    heat: float = 0.0                         # acessibilidade por uso (não verdade)
    # --- estado cognitivo próprio ---
    accessibility_level: str = "none"
    review_due: bool = False
    pinned: bool = False
    tags: tuple = ()

    @property
    def cost_min(self) -> float:
        """Custo operacional: leitura estimada (150 wpm, piso 2 min)."""
        return max(2.0, round(self.words / 150.0, 1))


def new_focus_goal(*, goal_id: str, title: str, root: str,
                   intent: str = "understand", priority: int = 3,
                   horizon_days: int = 30,
                   time_available_min: int | None = None,
                   depth_desired: dict | None = None,
                   excluded: list | None = None,
                   pinned: list | None = None) -> dict:
    """Constrói e VALIDA um FocusGoal (dict — serialização direta)."""
    if not title or not root:
        raise ValueError("objetivo exige title e root")
    if intent not in GOAL_INTENTS:
        raise ValueError(f"intent ∈ {GOAL_INTENTS}")
    if not 1 <= int(priority) <= 5:
        raise ValueError("priority: escala 1..5")
    depth = {d: 1 for d in ("conceptual",)}
    for dim, val in (depth_desired or {}).items():
        if dim not in DEPTH_DIMENSIONS:
            raise ValueError(f"dimensão desconhecida: {dim}")
        if not 0 <= int(val) <= 3:
            raise ValueError(f"profundidade {dim}: escala 0..3")
        depth[dim] = int(val)
    return {"id": goal_id, "title": title, "root": root, "intent": intent,
            "priority": int(priority), "horizon_days": int(horizon_days),
            "time_available_min": time_available_min,
            "depth_desired": depth,
            "excluded": sorted(set(excluded or [])),
            "pinned": sorted(set(pinned or [])),
            "status": "active"}


@dataclass
class ScoredItem:
    view: KnowledgeItemView
    score: float
    components: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)
