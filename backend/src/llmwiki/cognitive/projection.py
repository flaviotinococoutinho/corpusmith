"""CognitiveProjectionGate → CognitiveWorkingSet (ADR-22/23).

`artifact recall ≠ state commitment`: a recuperação produz CANDIDATOS;
este gate decide o que entra no working set — uma projeção temporária,
LIMITADA (orçamento explícito), explicável e reconstruível. Reduzir o
orçamento nunca aumenta o conteúdo projetado (propriedade testada).
Nada aqui escreve em lugar nenhum: candidatos entram, projeção sai.
"""
from __future__ import annotations
from .gates import hard_gates
from .model import KnowledgeItemView
from .scoring import cognitive_priority


def build_working_set(candidates: list[KnowledgeItemView], goal: dict,
                      policy: dict) -> dict:
    budgets = policy["budgets"]
    excluded, scored = [], []
    for view in candidates:
        ok, refused = hard_gates(view, goal, policy)
        if not ok:
            excluded.append({"page": view.page, "refused": refused})
            continue
        scored.append(cognitive_priority(view, goal, policy))
    scored.sort(key=lambda s: (-s.score, s.view.cost_min, s.view.page))

    items, questions, trimmed, spent = [], [], [], 0.0
    for s in scored:
        entry = {"page": s.view.page, "title": s.view.title,
                 "type": s.view.type, "score": s.score,
                 "components": s.components, "reasons": s.reasons,
                 "cost_min": s.view.cost_min,
                 "accessibility_level": s.view.accessibility_level,
                 "epistemic": {"confidence": s.view.epistemic_confidence,
                               "stale": s.view.stale,
                               "contested": s.view.contested},
                 "pinned": s.view.pinned}
        if s.view.type == "question":
            if len(questions) < budgets["max_questions"]:
                questions.append(entry)
            else:
                trimmed.append({"page": s.view.page,
                                "why": "orçamento de perguntas abertas"})
            continue
        if len(items) >= budgets["max_items"]:
            trimmed.append({"page": s.view.page,
                            "why": "orçamento de conceitos (max_items)"})
            continue
        if spent + s.view.cost_min > budgets["max_cost_min"] \
                and not s.view.pinned and s.view.page != goal["root"]:
            trimmed.append({"page": s.view.page,
                            "why": "orçamento de custo (max_cost_min)"})
            continue
        items.append(entry)
        spent += s.view.cost_min
    return {"goal_id": goal["id"], "policy_version": policy["version"],
            "budgets": dict(budgets),
            "items": items, "open_questions": questions,
            "cost_min": round(spent, 1),
            "considered": len(candidates),
            "eligible": len(scored),
            "excluded_by_gate": excluded,
            "trimmed_by_budget": trimmed}
