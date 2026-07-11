"""Estado contextual declarado (v0.18) — Cognitive Load Theory aplicada.

Sweller ("Cognitive load during problem solving", Cognitive Science,
1988): a capacidade de processar material novo é limitada e varia; a
entrega deve caber na carga disponível. Transposição local-first e
NÃO-invasiva: o estado é sempre DECLARADO pela pessoa (carga, foco,
energia, minutos), nunca inferido de comportamento — princípio "sinal
humano acima de inferência" + proteção de dado sensível. O estado tem
validade (TTL): passou o prazo, o sistema volta ao neutro em vez de
carregar um humor de ontem para as respostas de hoje.

Aqui também mora o vocabulário de ESTRATÉGIAS de explicação — os
experts do Hedge da resposta adaptativa (ask_memory as usa; o
RecordOutcome as treina).
"""
from __future__ import annotations
import time
from .base import UseCase
from ..runtime.db import connect
from ..settings import Settings

STRATEGIES = ("direta", "analogia-primeiro", "exemplo-primeiro",
              "teoria-primeiro", "decomposicao")

NEUTRAL = {"load": 3, "focus": 3, "energy": 3,
           "time_available_min": None, "note": None, "declared": False}


def current_state(settings: Settings) -> dict:
    """Estado vigente: a última declaração DENTRO do TTL; senão, neutro
    (carga média — o sistema não presume nem cansaço nem frescor)."""
    ttl_s = float(settings.get("cognitive.state_ttl_hours", 8)) * 3600
    rt = connect(settings.app_support / "runtime.db")
    row = rt.execute("SELECT ts, load, focus, energy, time_available_min, "
                     "note FROM cognitive_state "
                     "ORDER BY id DESC LIMIT 1").fetchone()
    rt.close()
    if not row or time.time() - row["ts"] > ttl_s:
        return dict(NEUTRAL)
    return {"load": row["load"], "focus": row["focus"],
            "energy": row["energy"],
            "time_available_min": row["time_available_min"],
            "note": row["note"], "declared": True,
            "age_min": round((time.time() - row["ts"]) / 60)}


def delivery_budget(settings: Settings, load: int) -> dict:
    """CLT em números: carga alta encolhe a entrega (menos evidências,
    resposta mais curta, instrução de concisão). Determinístico e puro
    em relação ao estado — testável sem modelo."""
    high = int(settings.get("cognitive.high_load", 4))
    if load >= high:
        return {"evidence_limit": 5, "max_tokens": 512, "concise": True}
    if load <= 2:
        return {"evidence_limit": 8, "max_tokens": 1536, "concise": False}
    return {"evidence_limit": 8, "max_tokens": 1024, "concise": False}


class DeclareCognitiveState(UseCase):
    def __init__(self, settings: Settings, *, load: int,
                 focus: int | None = None, energy: int | None = None,
                 time_available_min: int | None = None,
                 note: str | None = None, notify=None):
        for name, value in (("load", load), ("focus", focus),
                            ("energy", energy)):
            if value is not None and not 1 <= int(value) <= 5:
                raise ValueError(f"{name}: escala 1..5")
        self._settings = settings
        self._row = (int(load),
                     int(focus) if focus is not None else None,
                     int(energy) if energy is not None else None,
                     int(time_available_min) if time_available_min else None,
                     note)
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        rt.execute("INSERT INTO cognitive_state"
                   "(load, focus, energy, time_available_min, note) "
                   "VALUES (?,?,?,?,?)", self._row)
        # o histórico é sinal, não dossiê: mantém as últimas 200 declarações
        rt.execute("DELETE FROM cognitive_state WHERE id NOT IN "
                   "(SELECT id FROM cognitive_state ORDER BY id DESC LIMIT 200)")
        rt.commit()
        rt.close()
        state = current_state(self._settings)
        self._notify("cognitive.state_declared", {"load": state["load"]})
        return state
