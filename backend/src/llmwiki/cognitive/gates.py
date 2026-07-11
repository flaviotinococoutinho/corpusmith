"""Hard gates de elegibilidade — REGRAS antes de RANKING (§7).

eligible = valid AND in_scope AND not_superseded AND privacy_allowed.
Prioridade alta jamais atropela um gate: primeiro o binário, depois o
contínuo. Cada recusa sai NOMEADA (explicabilidade é contrato).
"""
from __future__ import annotations
from .model import KnowledgeItemView


def hard_gates(view: KnowledgeItemView, goal: dict,
               policy: dict) -> tuple[bool, list]:
    """(elegível?, motivos de recusa). Motivos vazios ⇒ passou."""
    refused = []
    if view.superseded:
        refused.append("superseded: substituída — nunca entra no working set")
    if view.invalid:
        refused.append("invalid: fora da validade bi-temporal")
    if view.page in goal.get("excluded", []):
        refused.append("excluded: ramo podado pelo usuário neste objetivo")
    if view.sensitive and not policy["gates"]["allow_sensitive"]:
        refused.append("privacy: sensível e a política não autoriza")
    if view.stale and not policy["gates"]["allow_stale"]:
        refused.append("stale: política exige conteúdo revisado")
    if view.contested and not policy["gates"]["allow_contested"]:
        refused.append("contested: política exclui disputas em aberto")
    if view.distance > policy["budgets"]["max_distance"] \
            and not view.pinned and view.page != goal["root"]:
        refused.append(f"scope: a {view.distance} saltos do raiz "
                       f"(máx {policy['budgets']['max_distance']})")
    return (not refused, refused)
