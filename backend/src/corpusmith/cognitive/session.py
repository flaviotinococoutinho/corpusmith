"""CognitiveSession + ResumeCapsule (ADR-25) — funções puras sobre dicts.

Leroy (2009), attention residue: trocar de contexto deixa resíduo; a
retomada barata exige que o CONTEXTO esteja fora da cabeça. A cápsula
captura objetivo, item atual, decisões, questões abertas, próximo passo
e a VERSÃO da política — retomar reconstrói a experiência sem exigir
memória humana. Máquina de estados explícita: active → suspended →
active → completed; transições inválidas recusam com erro.
"""
from __future__ import annotations
from .model import EXPERIENCE_MODES

SESSION_STATES = ("active", "suspended", "completed")


def new_session(*, session_id: str, goal: dict, projection_id: str,
                working_set: dict, mode: str, cognitive_state: dict,
                now: float) -> dict:
    if mode not in EXPERIENCE_MODES:
        raise ValueError(f"mode ∈ {EXPERIENCE_MODES}")
    return {"id": session_id, "goal_id": goal["id"],
            "projection_id": projection_id, "mode": mode,
            "state": "active", "working_set": working_set,
            "cognitive_state": cognitive_state,
            "policy_version": working_set["policy_version"],
            "steps": [], "open_questions":
                [q["page"] for q in working_set.get("open_questions", [])],
            "current_item": (working_set["items"][0]["page"]
                             if working_set["items"] else None),
            "capsule": None, "started_at": now,
            "suspended_at": None, "resumed_at": None, "completed_at": None}


def add_step(session: dict, *, kind: str, now: float, item: str | None = None,
             note: str | None = None, ref: str | None = None) -> dict:
    if session["state"] != "active":
        raise ValueError(f"sessão {session['state']}: passo exige active")
    step = {"kind": kind, "at": now}
    if item:
        step["item"] = item
        session["current_item"] = item
    if note:
        step["note"] = note
    if ref:
        step["ref"] = ref
    session["steps"].append(step)
    return step


def make_capsule(session: dict, *, reason: str, next_step: str | None,
                 now: float) -> dict:
    decisions = [s for s in session["steps"] if s["kind"] == "decision"]
    return {"goal_id": session["goal_id"], "mode": session["mode"],
            "current_item": session["current_item"],
            "steps_done": len(session["steps"]),
            "last_decision": decisions[-1]["note"] if decisions else None,
            "open_questions": list(session["open_questions"]),
            "next_step": next_step, "reason": reason,
            "policy_version": session["policy_version"],
            "suspended_at": now}


def suspend_session(session: dict, *, reason: str,
                    next_step: str | None, now: float) -> dict:
    """active → suspended; devolve a cápsula (também gravada na sessão)."""
    if session["state"] != "active":
        raise ValueError(f"suspender exige active (está {session['state']})")
    capsule = make_capsule(session, reason=reason, next_step=next_step,
                           now=now)
    session["state"] = "suspended"
    session["suspended_at"] = now
    session["capsule"] = capsule
    return capsule


def resume_session(session: dict, *, now: float) -> dict:
    """suspended → active; a cápsula orienta a reconstrução (objetivo,
    questões abertas e próximo passo intactos — propriedade testada)."""
    if session["state"] != "suspended":
        raise ValueError(f"retomar exige suspended (está {session['state']})")
    session["state"] = "active"
    session["resumed_at"] = now
    session["steps"].append({"kind": "resume", "at": now,
                             "note": session["capsule"]["next_step"]})
    return session["capsule"]


def complete_session(session: dict, *, now: float) -> dict:
    if session["state"] != "active":
        raise ValueError("concluir exige active")
    session["state"] = "completed"
    session["completed_at"] = now
    return session
