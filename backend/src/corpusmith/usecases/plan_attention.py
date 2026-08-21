"""Economia de atenção (v0.18) — "qual o melhor investimento dos
próximos N minutos?" respondido com o que a memória JÁ sabe.

Três fontes de candidatos, todas explicáveis:
- REVISÃO: páginas quentes cujo P(recall) ACT-R está na zona de esforço
  produtivo — valor = review_gain(p) = 4p(1−p) (dificuldade desejável,
  Bjork 1994); revisar o trivial ou o perdido rende pouco.
- LACUNAS: perguntas abertas, páginas contestadas e stale — o trabalho
  epistêmico pendente que o próprio Harness aponta.
- INBOX: fontes ainda não compiladas (captura barata esperando
  consolidação — o lado hipocampal do CLS).

Custo = leitura estimada (150 palavras/min, piso de 2 min). A seleção é
a mochila gulosa por densidade valor/custo (kernel.attention) dentro do
orçamento declarado; sob carga alta (CLT) só entram blocos pequenos —
menos material novo, mais consolidação. Cada item sai com `reason`:
recomendação sem porquê não entra na interface.
"""
from __future__ import annotations
import time
from .base import UseCase
from .cognitive_state import current_state
from ..kernel.activation import base_level_activation, retrieval_probability
from ..kernel.attention import fill_budget, review_gain
from ..kernel.vitality import aposentada, filtrar, vivas
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..settings import Settings

_WPM = 150.0
_MIN_COST = 2.0
_GAP_VALUE = {"question": 0.9, "low_yield": 0.8, "stale": 0.6,
              "inbox": 0.5}


def _cost(words: int) -> float:
    return max(_MIN_COST, round(words / _WPM, 1))


def paginas_vivas(settings: Settings) -> set[str]:
    """Alvos que ainda aceitam trabalho novo (F3-PR2, P-3).

    UMA leitura do bundle, compartilhada por todas as fontes da fila. Antes
    cada uma decidia sozinha o que contava — e `review_items`, que lê
    `page_heat` (histórico de uso por caminho, sem confronto com a
    autoridade), propunha revisar página aposentada e até página que nunca
    existiu. Medido."""
    reader = BundleReader(settings.path("knowledge") / "bundle")
    return vivas({d.rel_path: d.meta.model_dump(exclude_none=True)
                  for d in reader.iter_concepts()})


# As três fontes viram funções de módulo (v1.8): PlanAttention monta a
# mochila com orçamento; NextActions (R3) as reusa como fila ranqueada.
def review_items(settings: Settings) -> list[dict]:
    rt = connect(settings.app_support / "runtime.db")
    rows = rt.execute(
        "SELECT path, reads + cites uses, first_seen FROM page_heat "
        "WHERE reads + cites > 0").fetchall()
    rt.close()
    idx = connect(settings.app_support / "index.db")
    now, out = time.time(), []
    noise = float(settings.get("memory.activation_noise", 0.4))
    for r in rows:
        age_days = max((now - (r["first_seen"] or now)) / 86400, 0.05)
        p = retrieval_probability(
            base_level_activation(r["uses"], age_days), noise=noise)
        gain = review_gain(p)
        if gain < 0.3:                     # trivial ou perdida: fora
            continue
        words = (idx.execute(
            "SELECT COALESCE(SUM(LENGTH(text)),0) c FROM chunks "
            "WHERE page = ?", (r["path"],)).fetchone()["c"] or 400) / 6
        out.append({"kind": "review", "target": r["path"],
                    "value": round(gain, 3), "cost_min": _cost(int(words)),
                    "reason": f"revisão no ponto de esforço produtivo "
                              f"(P(recall)={p:.2f} ⇒ ganho {gain:.2f})"})
    idx.close()
    return filtrar(out, paginas_vivas(settings))


def gap_items(settings: Settings) -> list[dict]:
    reader = BundleReader(settings.path("knowledge") / "bundle")
    idx = connect(settings.app_support / "index.db")
    low_yield = {r["page"] for r in idx.execute(
        "SELECT page FROM page_overlay WHERE status = 'low_yield'")}
    idx.close()
    out = []
    for doc in reader.iter_concepts():
        meta = doc.meta.model_dump(exclude_none=True)
        words = len(doc.body.split())
        # F3-PR2: sucedida ou invalidada não é alvo de trabalho NOVO — e uma
        # pergunta FECHADA (`answered_by`) muito menos: era o item de maior
        # valor da fila (0.9) e voltava toda vez, mesmo depois de respondida
        if aposentada(meta) or meta.get("answered_by"):
            continue
        if doc.meta.type == "question":
            kind, reason = "question", "pergunta aberta na sua memória"
        elif doc.rel_path in low_yield:
            kind, reason = "low_yield", ("página de baixo rendimento — "
                                         "os desfechos dizem beco; editar "
                                         "ou aposentar vale mais que reler")
        elif meta.get("stale_as_of"):
            kind, reason = "stale", "marcada stale: revisar ou suceder"
        else:
            continue
        out.append({"kind": kind, "target": doc.rel_path,
                    "value": _GAP_VALUE[kind],
                    "cost_min": _cost(words + 200), "reason": reason})
    return out


def inbox_items(settings: Settings) -> list[dict]:
    kb = settings.path("knowledge")
    rt = connect(settings.app_support / "runtime.db")
    cached = {r["source"] for r in
              rt.execute("SELECT source FROM compile_cache")}
    rt.close()
    out = []
    for path in sorted((kb / "raw").rglob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        rel = str(path.relative_to(kb))
        if rel in cached:
            continue
        words = len(path.read_text(errors="ignore").split())
        out.append({"kind": "inbox", "target": rel,
                    "value": _GAP_VALUE["inbox"], "cost_min": _cost(words),
                    "reason": "fonte capturada e ainda não absorvida "
                              "(compile ou consolidação)"})
    return out


class PlanAttention(UseCase):
    def __init__(self, settings: Settings, *, minutes: int | None = None):
        self._settings = settings
        self._minutes = minutes

    def execute(self) -> dict:
        state = current_state(self._settings)
        budget = float(self._minutes or state["time_available_min"] or 60)
        high_load = state["load"] >= int(
            self._settings.get("cognitive.high_load", 4))
        items = (review_items(self._settings) + gap_items(self._settings)
                 + inbox_items(self._settings))
        if high_load:  # CLT: sob carga alta, só blocos pequenos e revisão
            items = [i for i in items
                     if i["kind"] == "review" or i["cost_min"] <= 10]
        plan = fill_budget(items, budget,
                           max_item_cost=15 if high_load else None)
        return {"budget_min": budget, "state": state,
                "high_load": high_load,
                "considered": len(items), "plan": plan}
