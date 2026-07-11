"""API do Cognitive Experience Domain (v0.19) — /cognitive/*.

Contratos orientados a caso de uso, HATEOAS em todo recurso (cada
resposta aponta as transições válidas do seu estado). Fala SÓ com a
CognitionFacade — regra de camadas garantida por teste.
"""
from __future__ import annotations
from fastapi import Depends, FastAPI, HTTPException
from .system import links
from ..facades import CognitionFacade
from ..settings import Settings


def mount_cognitive(app: FastAPI, s: Settings, bus, auth) -> None:
    cognition = CognitionFacade(s)
    emit = lambda t, d: bus.emit("cognitive", t, d)   # noqa: E731

    def _goal_links(goal_id: str) -> dict:
        return links(self=f"/cognitive/goals/{goal_id}",
                     project="/cognitive/projections",
                     goals="/cognitive/goals")

    def _session_links(session: dict) -> dict:
        base = f"/cognitive/sessions/{session['id']}"
        rels = {"self": base}
        if session["state"] == "active":
            rels.update(attempt=f"{base}/attempts",
                        feedback=f"{base}/feedback",
                        suspend=f"{base}/suspend",
                        complete=f"{base}/complete")
        elif session["state"] == "suspended":
            rels["resume"] = f"{base}/resume"
        return links(**rels)

    @app.post("/cognitive/goals", dependencies=[Depends(auth)])
    def create_goal(body: dict):
        try:
            goal = cognition.create_goal(body, notify=emit)
        except (KeyError, ValueError) as e:
            raise HTTPException(404 if isinstance(e, KeyError) else 400,
                                str(e))
        return {**goal, "_links": _goal_links(goal["id"])}

    @app.get("/cognitive/goals", dependencies=[Depends(auth)])
    def goals():
        return {"goals": cognition.goals(),
                "_links": links(self="/cognitive/goals",
                                create="/cognitive/goals")}

    @app.get("/cognitive/goals/{goal_id}", dependencies=[Depends(auth)])
    def goal(goal_id: str):
        try:
            found = cognition.goal(goal_id)
        except KeyError:
            raise HTTPException(404)
        return {**found, "_links": _goal_links(goal_id)}

    @app.post("/cognitive/projections", dependencies=[Depends(auth)])
    def project(body: dict):
        """{goal_id, policy?, pin?, exclude?} → nova projeção (imutável;
        fixar/excluir geram outra geração)."""
        try:
            result = cognition.build_projection(
                body["goal_id"], body.get("policy"),
                pin=body.get("pin"), exclude=body.get("exclude"),
                notify=emit)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {**result,
                "_links": links(
                    self=f"/cognitive/projections/{result['id']}",
                    start_session="/cognitive/sessions",
                    revise="/cognitive/projections")}

    @app.get("/cognitive/projections/{projection_id}",
             dependencies=[Depends(auth)])
    def projection(projection_id: str):
        try:
            found = cognition.projection(projection_id)
        except KeyError:
            raise HTTPException(404)
        return {**found,
                "_links": links(self=f"/cognitive/projections/{projection_id}",
                                start_session="/cognitive/sessions")}

    @app.post("/cognitive/sessions", dependencies=[Depends(auth)])
    def start_session(body: dict):
        try:
            session = cognition.start_session(
                body["projection_id"], body.get("mode", "understand"),
                notify=emit)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {**session, "_links": _session_links(session)}

    @app.get("/cognitive/sessions/{session_id}",
             dependencies=[Depends(auth)])
    def session(session_id: str):
        try:
            found = cognition.session(session_id)
        except KeyError:
            raise HTTPException(404)
        return {**found, "_links": _session_links(found)}

    @app.post("/cognitive/sessions/{session_id}/attempts",
              dependencies=[Depends(auth)])
    def attempt(session_id: str, body: dict):
        try:
            result = cognition.submit_attempt(session_id, body, notify=emit)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e))
        return {**result,
                "_links": links(session=f"/cognitive/sessions/{session_id}",
                                reviews="/cognitive/reviews/due")}

    @app.post("/cognitive/sessions/{session_id}/feedback",
              dependencies=[Depends(auth)])
    def feedback(session_id: str, body: dict):
        try:
            return cognition.record_feedback(session_id, body, notify=emit)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/cognitive/sessions/{session_id}/suspend",
              dependencies=[Depends(auth)])
    def suspend(session_id: str, body: dict | None = None):
        body = body or {}
        try:
            result = cognition.suspend_session(
                session_id, reason=body.get("reason", ""),
                next_step=body.get("next_step"), notify=emit)
        except KeyError:
            raise HTTPException(404)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return {**result,
                "_links": links(
                    resume=f"/cognitive/sessions/{session_id}/resume",
                    session=f"/cognitive/sessions/{session_id}")}

    @app.post("/cognitive/sessions/{session_id}/resume",
              dependencies=[Depends(auth)])
    def resume(session_id: str):
        try:
            session = cognition.resume_session(session_id, notify=emit)
        except KeyError:
            raise HTTPException(404)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return {**session, "_links": _session_links(session)}

    @app.post("/cognitive/sessions/{session_id}/complete",
              dependencies=[Depends(auth)])
    def complete(session_id: str):
        try:
            session = cognition.complete_session(session_id, notify=emit)
        except KeyError:
            raise HTTPException(404)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return {**session, "_links": links(
            goals="/cognitive/goals", reviews="/cognitive/reviews/due")}

    @app.get("/cognitive/reviews/due", dependencies=[Depends(auth)])
    def reviews_due(limit: int = 30):
        return {"reviews": cognition.due_reviews(limit),
                "_links": links(self="/cognitive/reviews/due")}

    @app.post("/cognitive/reviews/{review_id}/complete",
              dependencies=[Depends(auth)])
    def review_complete(review_id: int):
        try:
            return cognition.complete_review(review_id, notify=emit)
        except KeyError as e:
            raise HTTPException(404, str(e))
