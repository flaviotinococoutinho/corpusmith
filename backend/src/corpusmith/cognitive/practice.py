"""Recuperação ativa e prática espaçada (ADR-26/27).

Roediger & Karpicke (2006): apresentação não é aprendizagem — o que
consolida é TENTAR recuperar. Cepeda et al. (2006): o espaçamento ótimo
cresce com o horizonte de retenção. Aqui, determinístico e auditável
(spaced-v1): sucesso multiplica o intervalo, falha reinicia, falha
CONFIANTE (sobreconfiança — o sinal de calibração mais caro) volta antes
de todo mundo. Nada aqui toca confiança epistemológica: só a escada de
acessibilidade e a agenda.
"""
from __future__ import annotations
from .model import ATTEMPT_RESULTS, EXERCISE_LEVEL, level_index


def update_accessibility(current: dict | None, exercise: str,
                         result: str) -> dict:
    """Escada de acessibilidade: sucesso valida o nível do exercício
    (sobe, nunca desce — falha zera a sequência, não o nível: perder o
    acesso hoje não desfaz o que já foi validado; a AGENDA cuida da
    reconsolidação)."""
    if exercise not in EXERCISE_LEVEL:
        raise ValueError(f"exercise ∈ {sorted(EXERCISE_LEVEL)}")
    if result not in ATTEMPT_RESULTS:
        raise ValueError(f"result ∈ {ATTEMPT_RESULTS}")
    state = dict(current or {"level": "none", "streak": 0, "attempts": 0})
    state["attempts"] = state.get("attempts", 0) + 1
    state["last_result"] = result
    if result == "success":
        achieved = EXERCISE_LEVEL[exercise]
        if level_index(achieved) > level_index(state.get("level", "none")):
            state["level"] = achieved
        state["streak"] = state.get("streak", 0) + 1
    elif result == "failure":
        state["streak"] = 0
    return state


def schedule_review(*, result: str, confidence_before: float,
                    previous_interval_days: float | None,
                    horizon_days: int, review_policy: dict) -> dict:
    """Próxima revisão (spaced-v1). Decisão + motivo, sempre juntos."""
    p = review_policy
    prev = previous_interval_days or p["base_interval_days"]
    if result == "failure":
        if confidence_before >= p["overconfidence_threshold"]:
            interval = p["overconfident_interval_days"]
            reason = (f"falha com confiança {confidence_before:.0%} — "
                      "sobreconfiança volta primeiro")
        else:
            interval = p["failure_interval_days"]
            reason = "falha de recuperação — reconsolidar amanhã"
    elif result == "partial":
        interval = prev * p["partial_growth"]
        reason = "recuperação parcial — intervalo cresce devagar"
    else:
        interval = prev * p["growth"]
        reason = (f"sucesso — espaçamento cresce ×{p['growth']} "
                  "(efeito de espaçamento)")
    ceiling = max(p["base_interval_days"],
                  horizon_days / max(1.0, p["horizon_fraction"]))
    if interval > ceiling:
        interval = ceiling
        reason += f"; teto do horizonte de {horizon_days}d"
    return {"algorithm": "spaced-v1",
            "interval_days": round(interval, 2),
            "reason": reason,
            "params": {"previous_interval_days": prev,
                       "confidence_before": confidence_before,
                       "result": result, "horizon_days": horizon_days}}
