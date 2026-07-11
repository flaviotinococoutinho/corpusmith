"""CognitionFacade — o convívio cognitivo (v0.18): estado declarado,
perfil, calibração, observações metacognitivas e economia de atenção.

O contrato do convívio: a memória ADAPTA a entrega ao estado e ao
perfil; a pessoa GOVERNA o que o sistema aprendeu sobre ela (toda
inferência passa pelo gate humano; aceite vira geração na linhagem de
configuração — auditável e reversível)."""
from __future__ import annotations
from ..settings import Settings
from ..usecases.cognitive_state import (DeclareCognitiveState, STRATEGIES,
                                        current_state)
from ..usecases.metacognition import (ObserveMetacognition,
                                      ReviewObservation, calibration_report,
                                      observations)
from ..usecases.plan_attention import PlanAttention
from ..runtime.db import connect


class CognitionFacade:
    def __init__(self, settings: Settings):
        self._settings = settings

    def declare_state(self, *, load: int, focus: int | None = None,
                      energy: int | None = None,
                      time_available_min: int | None = None,
                      note: str | None = None, notify=None) -> dict:
        return DeclareCognitiveState(
            self._settings, load=load, focus=focus, energy=energy,
            time_available_min=time_available_min, note=note,
            notify=notify).execute()

    def state(self) -> dict:
        return current_state(self._settings)

    def overview(self) -> dict:
        """Visão única do painel: estado · perfil declarado · crédito das
        estratégias (observado) · calibração · contagem de observações."""
        rt = connect(self._settings.app_support / "runtime.db")
        weights = {r["strategy"]: r["weight"] for r in rt.execute(
            "SELECT strategy, weight FROM strategy_weights")}
        pending = rt.execute("SELECT COUNT(*) c FROM metacog_observations "
                             "WHERE status = 'proposed'").fetchone()["c"]
        rt.close()
        return {"state": current_state(self._settings),
                "profile": dict(self._settings.profile),
                "strategies": {s: weights.get(s, 1.0) for s in STRATEGIES},
                "calibration": calibration_report(self._settings),
                "pending_observations": pending}

    def observe(self, notify=None) -> dict:
        return ObserveMetacognition(self._settings, notify).execute()

    def observations(self, status: str | None = None) -> list[dict]:
        return observations(self._settings, status)

    def review_observation(self, observation_id: int, action: str,
                           notify=None) -> dict:
        return ReviewObservation(self._settings, observation_id, action,
                                 notify).execute()

    def attention_plan(self, minutes: int | None = None) -> dict:
        return PlanAttention(self._settings, minutes=minutes).execute()
