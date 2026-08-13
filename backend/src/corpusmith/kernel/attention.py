"""Economia de atenção (v0.18) — tempo como recurso escasso, formalizado.

Duas peças puras:

1. `review_gain(p)` = 4·p·(1−p) — o ganho esperado de REVISAR uma
   memória com probabilidade de recuperação p (ACT-R) segue a lógica das
   "dificuldades desejáveis" (Bjork, "Memory and metamemory
   considerations in the training of human beings", 1994; Roediger &
   Karpicke, "The power of testing memory", 2006): revisar o que se
   recupera com esforço-mas-sucesso vale mais que o trivial (p≈1, nada a
   consolidar) ou o perdido (p≈0, é reaprendizado, não revisão). A forma
   4p(1−p) é a variância de Bernoulli normalizada — máxima incerteza,
   máxima informação por minuto — com pico em p = 0.5.

2. `fill_budget` — mochila gulosa por DENSIDADE de valor (valor/custo),
   a heurística de Dantzig (1957) para a mochila fracionária: ordenar
   por densidade e encher até o orçamento. Itens aqui são indivisíveis,
   mas com custos pequenos versus o orçamento o guloso fica perto do
   ótimo — e é explicável ("entrou porque rende X por minuto"), o que
   nenhum solver dá de graça.

Puro: stdlib somente.
"""
from __future__ import annotations


def review_gain(recall_probability: float) -> float:
    """4p(1−p) ∈ [0,1]: pico no ponto de esforço produtivo (p=0.5)."""
    p = max(0.0, min(1.0, recall_probability))
    return 4.0 * p * (1.0 - p)


def fill_budget(items: list[dict], budget_min: float,
                max_item_cost: float | None = None) -> list[dict]:
    """Guloso por densidade valor/custo até estourar o orçamento.
    Cada item precisa de `value` e `cost_min` (> 0); `max_item_cost`
    poda itens grandes ANTES (carga alta ⇒ só blocos pequenos).
    Devolve os escolhidos com `density`, na ordem de recomendação."""
    viable = [dict(i) for i in items
              if i.get("cost_min", 0) > 0
              and (max_item_cost is None or i["cost_min"] <= max_item_cost)]
    for item in viable:
        item["density"] = item["value"] / item["cost_min"]
    viable.sort(key=lambda i: (-i["density"], i["cost_min"]))
    chosen, spent = [], 0.0
    for item in viable:
        if spent + item["cost_min"] <= budget_min:
            chosen.append(item)
            spent += item["cost_min"]
    return chosen
