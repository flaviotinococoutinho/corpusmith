"""Prioridade cognitiva — configurável, decomposta, explicada (§7).

score = Σ wᵢ·componenteᵢ − w_custo·custo. Componentes ∈ [0,1], cada um de
UMA família de peso (cognitivo, estrutural, agenda, operacional); a
decomposição sai junto do número — um score sem componentes não sobe à
interface. Monotônico por construção: subir user_focus (mantido o resto)
nunca reduz o score (propriedade testada).
"""
from __future__ import annotations
from .model import ACCESS_LEVELS, KnowledgeItemView, ScoredItem, level_index


def _gap(view: KnowledgeItemView, goal: dict) -> float:
    """Lacuna = distância entre o nível de acessibilidade validado e a
    profundidade desejada média do objetivo (0..3 → alvo na escada)."""
    desired = goal.get("depth_desired") or {"conceptual": 1}
    mean_desired = sum(desired.values()) / max(1, len(desired))   # 0..3
    target = min(len(ACCESS_LEVELS) - 1, 1 + round(mean_desired * 1.6))
    have = level_index(view.accessibility_level)
    if target <= 0:
        return 0.0
    return max(0.0, (target - have) / target)


def cognitive_priority(view: KnowledgeItemView, goal: dict,
                       policy: dict) -> ScoredItem:
    w = policy["weights"]
    components = {
        "user_focus": 1.0 if (view.pinned or view.page == goal["root"])
                      else max(0.0, 1.0 - 0.3 * view.distance)
                      * (goal.get("priority", 3) / 5.0),
        "goal_alignment": 1.0 / (1.0 + view.distance),
        "knowledge_gap": _gap(view, goal),
        "dependency_unlock": min(1.0, view.degree / 6.0),
        "review_urgency": 1.0 if view.review_due else 0.0,
        "accessibility_heat": max(0.0, min(1.0, view.heat)),
        "cost_penalty": min(1.0, view.cost_min / 30.0),
    }
    score = sum(w[k] * v for k, v in components.items()
                if k != "cost_penalty")
    score -= w["cost_penalty"] * components["cost_penalty"]
    reasons = []
    if view.pinned:
        reasons.append("fixado pelo usuário neste objetivo")
    elif view.page == goal["root"]:
        reasons.append("é o conceito raiz do objetivo")
    if components["knowledge_gap"] >= 0.5:
        reasons.append(
            f"profundidade validada ({view.accessibility_level}) abaixo "
            f"da desejada — lacuna {components['knowledge_gap']:.0%}")
    if view.review_due:
        reasons.append("revisão vencida na agenda espaçada")
    if components["dependency_unlock"] >= 0.5:
        reasons.append(f"nó conectivo: destrava {view.degree} vizinhos")
    if view.stale:
        reasons.append("⚠ marcada stale no canônico — ler com reserva")
    if view.contested:
        reasons.append("⚔ contestada no canônico — há disputa aberta")
    if not reasons:
        reasons.append(f"a {view.distance} salto(s) do raiz, "
                       f"custo {view.cost_min:.0f} min")
    return ScoredItem(view=view, score=round(max(0.0, score), 4),
                      components={k: round(v, 4)
                                  for k, v in components.items()},
                      reasons=reasons)
