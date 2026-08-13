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
from ..usecases.cognitive_journey import (BuildProjection,
                                          CompleteCognitiveSession,
                                          CompleteReview, CreateFocusGoal,
                                          RecordCognitiveFeedback,
                                          ResumeCognitiveSession,
                                          StartCognitiveSession,
                                          SubmitRetrievalAttempt,
                                          SuspendCognitiveSession,
                                          due_reviews, get_goal,
                                          get_projection, get_session,
                                          list_goals)
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

    # ------------------------------- jornada de exploração focada (v0.19)
    def create_goal(self, body: dict, notify=None) -> dict:
        return CreateFocusGoal(self._settings, body, notify).execute()

    def goal(self, goal_id: str) -> dict:
        return get_goal(self._settings, goal_id)

    def goals(self) -> list[dict]:
        return list_goals(self._settings)

    def build_projection(self, goal_id: str, policy: dict | None = None, *,
                         pin: str | None = None, exclude: str | None = None,
                         notify=None) -> dict:
        return BuildProjection(self._settings, goal_id, policy,
                               pin=pin, exclude=exclude,
                               notify=notify).execute()

    def projection(self, projection_id: str) -> dict:
        return get_projection(self._settings, projection_id)

    def start_session(self, projection_id: str, mode: str = "understand",
                      notify=None) -> dict:
        return StartCognitiveSession(self._settings, projection_id, mode,
                                     notify).execute()

    def session(self, session_id: str) -> dict:
        return get_session(self._settings, session_id)

    def submit_attempt(self, session_id: str, body: dict,
                       notify=None) -> dict:
        return SubmitRetrievalAttempt(self._settings, session_id, body,
                                      notify).execute()

    def record_feedback(self, session_id: str | None, body: dict,
                        notify=None) -> dict:
        return RecordCognitiveFeedback(self._settings, session_id, body,
                                       notify).execute()

    def suspend_session(self, session_id: str, *, reason: str = "",
                        next_step: str | None = None, notify=None) -> dict:
        return SuspendCognitiveSession(self._settings, session_id,
                                       reason=reason, next_step=next_step,
                                       notify=notify).execute()

    def resume_session(self, session_id: str, notify=None) -> dict:
        return ResumeCognitiveSession(self._settings, session_id,
                                      notify).execute()

    def complete_session(self, session_id: str, notify=None) -> dict:
        return CompleteCognitiveSession(self._settings, session_id,
                                        notify).execute()

    def due_reviews(self, limit: int = 30) -> list[dict]:
        return due_reviews(self._settings, limit)

    def complete_review(self, review_id: int, notify=None) -> dict:
        return CompleteReview(self._settings, review_id, notify).execute()

    # -------------------------------------------------------------- v0.20
    def goal_progress(self, goal_id: str) -> dict:
        from ..usecases.cognitive_journey import goal_progress
        return goal_progress(self._settings, goal_id)

    def report_experience(self, body: dict, notify=None) -> dict:
        from ..usecases.cognitive_journey import ReportMetacognitiveExperience
        return ReportMetacognitiveExperience(self._settings, body,
                                             notify).execute()

    def register_analogy(self, body: dict, notify=None) -> dict:
        from ..usecases.cognitive_journey import RegisterAnalogy
        return RegisterAnalogy(self._settings, body, notify).execute()

    def analogies(self) -> list[dict]:
        from ..usecases.cognitive_journey import list_analogies
        return list_analogies(self._settings)

    def promote_analogy(self, analogy_id: str, notify=None) -> dict:
        from ..usecases.cognitive_journey import PromoteAnalogy
        return PromoteAnalogy(self._settings, analogy_id, notify).execute()

    def curation_projection(self, limit: int = 20) -> dict:
        from ..usecases.cognitive_journey import curation_projection
        return curation_projection(self._settings, limit)

    def cognitive_metrics(self) -> dict:
        from ..usecases.cognitive_journey import cognitive_metrics
        return cognitive_metrics(self._settings)

    def exercise_prompt(self, exercise: str, title: str,
                        item: str | None = None) -> dict:
        from ..usecases.cognitive_journey import prompt_for
        return prompt_for(self._settings, exercise, title, item)

    def episodes(self, limit: int = 40) -> list[dict]:
        from ..usecases.cognitive_journey import episodes
        return episodes(self._settings, limit)
