"""CognitivePolicy — declarativa, versionada, validada, reversível.

Nenhum número psicológico universal: os limites do working set (Baddeley
como RESTRIÇÃO de engenharia, não como constante mágica) e todos os
coeficientes do score são dados configuráveis. A política persiste com a
projeção (snapshot) — reproduzir uma projeção antiga usa a política da
época, não a atual.
"""
from __future__ import annotations
import copy

# pesos do score cognitivo — famílias separadas (ADR-20/§6): cognitivo
# (foco/alinhamento/lacuna), estrutural (unlock), operacional (custo) e
# agenda (urgência de revisão). Nada disso é peso epistemológico.
DEFAULT_POLICY = {
    "version": 1,
    "weights": {
        "user_focus": 0.22,
        "goal_alignment": 0.18,
        "knowledge_gap": 0.22,
        "dependency_unlock": 0.12,
        "review_urgency": 0.12,
        "accessibility_heat": 0.04,
        "expected_information_gain": 0.06,   # VoI (v0.21): lacuna×unlock
        "cost_penalty": 0.08,          # subtrai — custo nunca soma
    },
    "budgets": {                        # working set LIMITADO e explícito
        "max_items": 7,
        "max_questions": 3,
        "max_cost_min": 90,
        "max_distance": 2,
    },
    "gates": {
        "allow_sensitive": False,
        "allow_stale": True,            # stale entra SINALIZADO (revisão)
        "allow_low_yield": True,        # baixo rendimento entra marcado
    },
    "review": {                         # prática espaçada (spaced-v1)
        "base_interval_days": 1.0,
        "growth": 2.2,                  # sucesso multiplica o intervalo
        "partial_growth": 1.2,
        "failure_interval_days": 1.0,
        "overconfident_interval_days": 0.5,   # conf. alta + falha ⇒ cedo
        "overconfidence_threshold": 0.7,
        "horizon_fraction": 3.0,        # intervalo ≤ horizonte/fração
    },
}


def _translate_legacy(policy: dict) -> dict:
    """F4-PR2 (ADR-52): `allow_contested` vive em snapshots PERSISTIDOS
    (cognitive.db). A chave legada é traduzida, nunca recusada — recusar
    invalidaria toda projeção gravada antes do rename."""
    gates = dict((policy or {}).get("gates", {}) or {})
    if "allow_contested" in gates:
        gates.setdefault("allow_low_yield", gates.pop("allow_contested"))
        policy = {**(policy or {}), "gates": gates}
    return policy


def validate_policy(policy: dict) -> dict:
    policy = _translate_legacy(policy)
    """Valida forma e domínios; devolve cópia normalizada (nunca muta)."""
    p = copy.deepcopy(DEFAULT_POLICY)
    for section in ("weights", "budgets", "gates", "review"):
        extra = (policy or {}).get(section, {})
        if not isinstance(extra, dict):
            raise ValueError(f"policy.{section}: esperado objeto")
        for key, value in extra.items():
            if key not in p[section]:
                raise ValueError(f"policy.{section}.{key}: desconhecida")
            if isinstance(p[section][key], bool):
                if not isinstance(value, bool):
                    raise ValueError(f"policy.{section}.{key}: booleano")
            elif not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"policy.{section}.{key}: número")
            elif value < 0:
                raise ValueError(f"policy.{section}.{key}: ≥ 0")
            p[section][key] = value
    if "version" in (policy or {}):
        p["version"] = int(policy["version"])
    return p
