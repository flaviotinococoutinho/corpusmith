"""cognitive/ — Cognitive Experience Domain (v0.19).

Domínio PURO (stdlib, zero I/O — mesma classe de pureza de kernel/ e
normalize/, garantida por teste de arquitetura). Representa "o que a
pessoa quer explorar agora, em que profundidade, com que esforço e por
qual estratégia" — nunca "o que é verdade".

Regra fundamental (ADR-21): este domínio SELECIONA, ORDENA, REDUZ,
EXPANDE, OCULTA e RECOMENDA projeções de conhecimento; ele NÃO altera
fatos, evidências, confiança epistemológica, temporalidade nem o grafo
canônico. A memória entra aqui como dado imutável (KnowledgeItemView,
montado pelos adapters); sai daqui como projeção explicável
(CognitiveWorkingSet) + estados próprios (acessibilidade, agenda,
sessão) que vivem em banco separado (cognitive.db).

    Knowledge & Memory Domain ──dados governados──▶ este plano
    este plano ──projeção configurável──▶ experiência (API/desktop)
"""
from .model import (ACCESS_LEVELS, DEPTH_DIMENSIONS, EXERCISE_LEVEL,
                    EXPERIENCE_MODES, FEEDBACK_SCOPES, FEEDBACK_VERDICTS,
                    KnowledgeItemView, level_index, new_focus_goal)
from .policy import DEFAULT_POLICY, validate_policy
from .gates import hard_gates
from .scoring import cognitive_priority
from .projection import build_working_set
from .practice import schedule_review, update_accessibility
from .session import (add_step, complete_session, make_capsule, new_session,
                      resume_session, suspend_session)

__all__ = [
    "ACCESS_LEVELS", "DEPTH_DIMENSIONS", "EXERCISE_LEVEL",
    "EXPERIENCE_MODES", "FEEDBACK_SCOPES", "FEEDBACK_VERDICTS",
    "KnowledgeItemView", "level_index", "new_focus_goal",
    "DEFAULT_POLICY", "validate_policy", "hard_gates",
    "cognitive_priority", "build_working_set", "schedule_review",
    "update_accessibility", "new_session", "add_step", "make_capsule",
    "suspend_session", "resume_session", "complete_session",
]
