"""Jornada cognitiva (v0.19) — adapters do Cognitive Experience Domain.

Este módulo é a PONTE: lê a memória governada (bundle + index.db +
runtime.db, somente leitura) e monta KnowledgeItemView; chama o domínio
puro (cognitive/) para projetar/pontuar/agendar; persiste APENAS estado
cognitivo em cognitive.db. Invariante de regressão epistemológica
(testado): nenhuma função aqui escreve no bundle, index.db, git ou
frontmatter.
"""
from __future__ import annotations
import json
import time
from .base import UseCase
from ..cognitive import (DEFAULT_POLICY, FEEDBACK_SCOPES, FEEDBACK_VERDICTS,
                         KnowledgeItemView, build_working_set,
                         complete_session, new_focus_goal, new_session,
                         resume_session, schedule_review, suspend_session,
                         update_accessibility, validate_policy)
from ..cognitive.session import add_step
from ..kernel.identity import factory as id_factory
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..settings import Settings
from .cognitive_state import current_state

_FOCUS_IDS = id_factory("focus")
_SESSION_IDS = id_factory("session")


def _cog(settings: Settings):
    return connect(settings.app_support / "cognitive.db")


# ------------------------------------------------------- leitura da memória
def _candidate_views(settings: Settings, goal: dict,
                     policy: dict) -> list[KnowledgeItemView]:
    """BFS no grafo canônico a partir do raiz (± max_distance) e montagem
    das views — TODO o estado epistemológico vem do canônico, somente
    leitura; acessibilidade/agenda vêm do cognitive.db."""
    idx = connect(settings.app_support / "index.db")
    adjacency: dict[str, set] = {}
    for src, dst in idx.execute("SELECT src, dst FROM graph_edges"):
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)
    distance = {goal["root"]: 0}
    frontier = [goal["root"]]
    while frontier:
        nxt = []
        for node in frontier:
            for neighbor in adjacency.get(node, ()):
                if neighbor not in distance:
                    distance[neighbor] = distance[node] + 1
                    if distance[neighbor] <= policy["budgets"]["max_distance"]:
                        nxt.append(neighbor)
        frontier = nxt
    for pin in goal.get("pinned", []):
        distance.setdefault(pin, policy["budgets"]["max_distance"])
    words = {r["page"]: (r["c"] or 0) / 6 for r in idx.execute(
        "SELECT page, SUM(LENGTH(text)) c FROM chunks GROUP BY page")}
    contested = {r["page"] for r in idx.execute(
        "SELECT page FROM page_overlay WHERE status='low_yield'")}
    idx.close()

    rt = connect(settings.app_support / "runtime.db")
    heat = {r["path"]: r["score"] or 0.0 for r in
            rt.execute("SELECT path, score FROM page_heat")}
    rt.close()

    cog = _cog(settings)
    access = {r["item"]: r["level"] for r in
              cog.execute("SELECT item, level FROM accessibility")}
    due = {r["item"] for r in cog.execute(
        "SELECT DISTINCT item FROM review_schedules "
        "WHERE status='due' AND due_at <= unixepoch('subsec')")}
    cog.close()

    now = time.time()
    views = []
    reader = BundleReader(settings.path("knowledge") / "bundle")
    for doc in reader.iter_concepts():
        page = doc.rel_path
        if page not in distance:
            continue
        meta = doc.meta.model_dump(exclude_none=True, mode="json")
        invalid_at = doc.meta.invalid_at
        views.append(KnowledgeItemView(
            page=page, title=doc.meta.title or page,
            type=doc.meta.type,
            epistemic_confidence=("human" if str(meta.get(
                "generated_via", "")).startswith("human")
                else meta.get("confidence", "extracted") or "extracted"),
            superseded=bool(meta.get("superseded_by")),
            invalid=bool(invalid_at and invalid_at.timestamp() <= now),
            stale=bool(meta.get("stale_as_of")),
            low_yield=page in contested,
            sensitive=bool(meta.get("sensitive_data")),
            distance=distance[page],
            degree=len(adjacency.get(page, ())),
            words=int(words.get(page, len(doc.body.split()))),
            heat=float(heat.get(page, 0.0)),
            accessibility_level=access.get(page, "none"),
            review_due=page in due,
            pinned=page in goal.get("pinned", []),
            tags=tuple(doc.meta.tags or ())))
    return views


def get_goal(settings: Settings, goal_id: str) -> dict:
    cog = _cog(settings)
    row = cog.execute("SELECT goal, status FROM focus_goals WHERE id=?",
                      (goal_id,)).fetchone()
    cog.close()
    if not row:
        raise KeyError(f"objetivo {goal_id}")
    return {**json.loads(row["goal"]), "status": row["status"]}


def list_goals(settings: Settings) -> list[dict]:
    cog = _cog(settings)
    rows = cog.execute("SELECT goal, status, created_at FROM focus_goals "
                       "ORDER BY created_at DESC LIMIT 50").fetchall()
    cog.close()
    return [{**json.loads(r["goal"]), "status": r["status"]} for r in rows]


def get_projection(settings: Settings, projection_id: str) -> dict:
    cog = _cog(settings)
    row = cog.execute("SELECT goal_id, policy, working_set, trace_id "
                      "FROM cognitive_projections WHERE id=?",
                      (projection_id,)).fetchone()
    cog.close()
    if not row:
        raise KeyError(f"projeção {projection_id}")
    return {"id": projection_id, "goal_id": row["goal_id"],
            "trace_id": row["trace_id"],
            "policy": json.loads(row["policy"]),
            "working_set": json.loads(row["working_set"])}


def get_session(settings: Settings, session_id: str) -> dict:
    cog = _cog(settings)
    row = cog.execute("SELECT session, trace_id FROM cognitive_sessions "
                      "WHERE id=?", (session_id,)).fetchone()
    cog.close()
    if not row:
        raise KeyError(f"sessão {session_id}")
    return {**json.loads(row["session"]), "trace_id": row["trace_id"]}


def _save_session(settings: Settings, session: dict) -> None:
    cog = _cog(settings)
    cog.execute("UPDATE cognitive_sessions SET session=?, state=?, "
                "updated_at=unixepoch('subsec') WHERE id=?",
                (json.dumps({k: v for k, v in session.items()
                             if k != "trace_id"}),
                 session["state"], session["id"]))
    cog.commit()
    cog.close()


def due_reviews(settings: Settings, limit: int = 30) -> list[dict]:
    cog = _cog(settings)
    rows = cog.execute(
        "SELECT r.id, r.item, r.due_at, r.interval_days, r.reason, "
        "r.algorithm, a.level, a.streak, a.last_result "
        "FROM review_schedules r LEFT JOIN accessibility a ON a.item=r.item "
        "WHERE r.status='due' AND r.due_at <= unixepoch('subsec') "
        "ORDER BY r.due_at LIMIT ?", (limit,)).fetchall()
    cog.close()
    from ..cognitive.progress import interleave, support_level
    out = []
    for r in rows:
        entry = dict(r)
        entry["support"] = support_level(entry.get("streak") or 0)
        out.append(entry)
    # intercalação (v0.21): alterna grupos — variar contexto de
    # recuperação discrimina conceitos vizinhos (Rohrer/Taylor)
    return interleave(out, "item")


# ------------------------------------------------------------- use cases
class CreateFocusGoal(UseCase):
    def __init__(self, settings: Settings, body: dict, notify=None):
        self._settings = settings
        self._body = body
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        goal = new_focus_goal(
            goal_id=_FOCUS_IDS.next_rendered(),
            title=self._body["title"], root=self._body["root"],
            intent=self._body.get("intent", "understand"),
            priority=self._body.get("priority", 3),
            horizon_days=self._body.get("horizon_days", 30),
            time_available_min=self._body.get("time_available_min"),
            depth_desired=self._body.get("depth_desired"),
            excluded=self._body.get("excluded"),
            pinned=self._body.get("pinned"))
        if not BundleReader(self._settings.path("knowledge") / "bundle") \
                .exists(goal["root"]):
            raise KeyError(f"conceito raiz inexistente: {goal['root']}")
        cog = _cog(self._settings)
        cog.execute("INSERT INTO focus_goals(id, goal) VALUES (?,?)",
                    (goal["id"], json.dumps(goal)))
        cog.commit()
        cog.close()
        self._notify("focus.goal.created", {"goal_id": goal["id"],
                                            "root": goal["root"]})
        return goal


class BuildProjection(UseCase):
    """Memória governada → gates → score → orçamento → working set.
    Revisões (fixar/excluir/adiar) geram NOVA projeção — versões
    imutáveis, como toda linhagem deste projeto."""

    def __init__(self, settings: Settings, goal_id: str,
                 policy: dict | None = None, *, pin: str | None = None,
                 exclude: str | None = None, notify=None):
        self._settings = settings
        self._goal_id = goal_id
        self._policy = validate_policy(policy or dict(DEFAULT_POLICY))
        self._pin, self._exclude = pin, exclude
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        goal = get_goal(self._settings, self._goal_id)
        if self._pin or self._exclude:              # revisão do usuário
            pinned = set(goal.get("pinned", []))
            excluded = set(goal.get("excluded", []))
            if self._pin:
                pinned.add(self._pin)
                excluded.discard(self._pin)
                self._notify("focus.node.promoted", {"page": self._pin})
            if self._exclude:
                excluded.add(self._exclude)
                pinned.discard(self._exclude)
                self._notify("focus.node.suppressed", {"page": self._exclude})
            goal["pinned"], goal["excluded"] = sorted(pinned), sorted(excluded)
            cog = _cog(self._settings)
            cog.execute("UPDATE focus_goals SET goal=?, "
                        "updated_at=unixepoch('subsec') WHERE id=?",
                        (json.dumps({k: v for k, v in goal.items()
                                     if k != "status"}), goal["id"]))
            cog.commit()
            cog.close()
        views = _candidate_views(self._settings, goal, self._policy)
        working_set = build_working_set(views, goal, self._policy)
        projection_id = _FOCUS_IDS.next_rendered()
        trace_id = _FOCUS_IDS.next_rendered()
        cog = _cog(self._settings)
        cog.execute("INSERT INTO cognitive_projections"
                    "(id, goal_id, policy, working_set, trace_id) "
                    "VALUES (?,?,?,?,?)",
                    (projection_id, goal["id"], json.dumps(self._policy),
                     json.dumps(working_set), trace_id))
        cog.commit()
        cog.close()
        self._notify("focus.projection.generated",
                     {"projection_id": projection_id, "goal_id": goal["id"],
                      "items": len(working_set["items"]),
                      "trace_id": trace_id})
        return {"id": projection_id, "goal_id": goal["id"],
                "trace_id": trace_id, "working_set": working_set}


class StartCognitiveSession(UseCase):
    def __init__(self, settings: Settings, projection_id: str,
                 mode: str = "understand", notify=None):
        self._settings = settings
        self._projection_id = projection_id
        self._mode = mode
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        projection = get_projection(self._settings, self._projection_id)
        goal = get_goal(self._settings, projection["goal_id"])
        session = new_session(
            session_id=_SESSION_IDS.next_rendered(), goal=goal,
            projection_id=self._projection_id,
            working_set=projection["working_set"], mode=self._mode,
            cognitive_state=current_state(self._settings), now=time.time())
        trace_id = _SESSION_IDS.next_rendered()
        cog = _cog(self._settings)
        cog.execute("INSERT INTO cognitive_sessions"
                    "(id, goal_id, projection_id, state, session, trace_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (session["id"], session["goal_id"], self._projection_id,
                     session["state"], json.dumps(session), trace_id))
        cog.commit()
        cog.close()
        self._notify("cognitive.session.started",
                     {"session_id": session["id"], "mode": self._mode,
                      "trace_id": trace_id})
        return {**session, "trace_id": trace_id}


class SubmitRetrievalAttempt(UseCase):
    """Recuperação ativa: confiança ANTES, resultado depois. Atualiza SÓ
    acessibilidade + agenda (nunca o canônico) e loga o passo na sessão."""

    def __init__(self, settings: Settings, session_id: str, body: dict,
                 notify=None):
        self._settings = settings
        self._session_id = session_id
        self._body = body
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        session = get_session(self._settings, self._session_id)
        item = self._body["item"]
        if item not in {i["page"] for i in session["working_set"]["items"]} \
                and item not in session["open_questions"]:
            raise ValueError(f"{item} não está no working set desta sessão")
        confidence = float(self._body["confidence_before"])
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence_before ∈ [0,1] — antes da resposta")
        exercise = self._body.get("exercise", "recall")
        result = self._body["result"]

        cog = _cog(self._settings)
        current = cog.execute("SELECT level, streak, attempts, last_result "
                              "FROM accessibility WHERE item=?",
                              (item,)).fetchone()
        state = update_accessibility(dict(current) if current else None,
                                     exercise, result)
        cog.execute("INSERT INTO accessibility(item, level, streak, attempts,"
                    " last_result, updated_at) VALUES (?,?,?,?,?,"
                    "unixepoch('subsec')) ON CONFLICT(item) DO UPDATE SET "
                    "level=excluded.level, streak=excluded.streak, "
                    "attempts=excluded.attempts, "
                    "last_result=excluded.last_result, "
                    "updated_at=excluded.updated_at",
                    (item, state["level"], state["streak"],
                     state["attempts"], state["last_result"]))
        cur = cog.execute(
            "INSERT INTO retrieval_attempts(session_id, item, exercise, "
            "prompt, answer, confidence_before, result, duration_s, "
            "support_used) VALUES (?,?,?,?,?,?,?,?,?)",
            (self._session_id, item, exercise, self._body.get("prompt"),
             self._body.get("answer"), confidence, result,
             self._body.get("duration_s"),
             int(bool(self._body.get("support_used")))))
        attempt_id = cur.lastrowid
        previous = cog.execute(
            "SELECT interval_days FROM review_schedules WHERE item=? "
            "ORDER BY id DESC LIMIT 1", (item,)).fetchone()
        goal = get_goal(self._settings, session["goal_id"])
        review = schedule_review(
            result=result, confidence_before=confidence,
            previous_interval_days=previous["interval_days"]
            if previous else None,
            horizon_days=goal["horizon_days"],
            review_policy=validate_policy({})["review"])
        cog.execute("UPDATE review_schedules SET status='cancelled' "
                    "WHERE item=? AND status='due'", (item,))
        cog.execute("INSERT INTO review_schedules(item, due_at, "
                    "interval_days, horizon_days, algorithm, params, reason) "
                    "VALUES (?, unixepoch('subsec') + ? * 86400, ?,?,?,?,?)",
                    (item, review["interval_days"], review["interval_days"],
                     goal["horizon_days"], review["algorithm"],
                     json.dumps(review["params"]), review["reason"]))
        cog.commit()
        cog.close()

        add_step(session, kind="attempt", now=time.time(), item=item,
                 note=f"{exercise}:{result}", ref=str(attempt_id))
        _save_session(self._settings, session)
        self._notify("retrieval.attempted",
                     {"session_id": self._session_id, "item": item,
                      "exercise": exercise, "result": result})
        self._notify(f"retrieval.{'succeeded' if result == 'success' else 'failed' if result == 'failure' else 'attempted'}",
                     {"item": item})
        self._notify("review.scheduled",
                     {"item": item, "in_days": review["interval_days"]})
        return {"attempt_id": attempt_id, "accessibility": state,
                "review": review,
                "calibration_gap": round(confidence - (
                    1.0 if result == "success" else 0.0), 3)}


class RecordCognitiveFeedback(UseCase):
    """Feedback = evento IMUTÁVEL, tipado, com escopo (§11)."""

    def __init__(self, settings: Settings, session_id: str | None,
                 body: dict, notify=None):
        self._settings = settings
        self._session_id = session_id
        self._body = body
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        scope, verdict = self._body.get("scope"), self._body.get("verdict")
        if scope not in FEEDBACK_SCOPES:
            raise ValueError(f"scope ∈ {FEEDBACK_SCOPES}")
        if verdict not in FEEDBACK_VERDICTS:
            raise ValueError(f"verdict ∈ {FEEDBACK_VERDICTS}")
        cog = _cog(self._settings)
        cur = cog.execute("INSERT INTO cognitive_feedback(session_id, scope, "
                          "target, verdict, note) VALUES (?,?,?,?,?)",
                          (self._session_id, scope, self._body.get("target"),
                           verdict, self._body.get("note")))
        cog.commit()
        feedback_id = cur.lastrowid
        cog.close()
        self._notify("feedback.recorded", {"scope": scope,
                                           "verdict": verdict})
        return {"feedback_id": feedback_id, "scope": scope,
                "verdict": verdict}


class SuspendCognitiveSession(UseCase):
    def __init__(self, settings: Settings, session_id: str, *,
                 reason: str = "", next_step: str | None = None, notify=None):
        self._settings = settings
        self._session_id = session_id
        self._reason = reason
        self._next_step = next_step
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        session = get_session(self._settings, self._session_id)
        capsule = suspend_session(session, reason=self._reason,
                                  next_step=self._next_step, now=time.time())
        _save_session(self._settings, session)
        self._notify("cognitive.session.suspended",
                     {"session_id": self._session_id})
        return {"session_id": self._session_id, "capsule": capsule}


class ResumeCognitiveSession(UseCase):
    def __init__(self, settings: Settings, session_id: str, notify=None):
        self._settings = settings
        self._session_id = session_id
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        session = get_session(self._settings, self._session_id)
        capsule = resume_session(session, now=time.time())
        _save_session(self._settings, session)
        self._notify("cognitive.session.resumed",
                     {"session_id": self._session_id})
        return {**session, "capsule": capsule}


class CompleteCognitiveSession(UseCase):
    def __init__(self, settings: Settings, session_id: str, notify=None):
        self._settings = settings
        self._session_id = session_id
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        session = get_session(self._settings, self._session_id)
        complete_session(session, now=time.time())
        _save_session(self._settings, session)
        self._notify("cognitive.session.completed",
                     {"session_id": self._session_id,
                      "steps": len(session["steps"])})
        return session


class CompleteReview(UseCase):
    def __init__(self, settings: Settings, review_id: int, notify=None):
        self._settings = settings
        self._review_id = int(review_id)
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        cog = _cog(self._settings)
        done = cog.execute("UPDATE review_schedules SET status='done', "
                           "completed_at=unixepoch('subsec') "
                           "WHERE id=? AND status='due'",
                           (self._review_id,)).rowcount
        cog.commit()
        cog.close()
        if not done:
            raise KeyError(f"revisão {self._review_id} não está devida")
        self._notify("review.completed", {"review_id": self._review_id})
        return {"review_id": self._review_id, "status": "done"}


# ============================== v0.20: profundidade · experiências ·
# analogias · projeção de curadoria · métricas · prompts
from ..cognitive.progress import (EXPERIENCE_TYPES, depth_progress,
                                  exercise_prompt, interleave, new_analogy,
                                  support_level)  # noqa: E402
from ..kernel.calibration import brier_score  # noqa: E402


def goal_progress(settings: Settings, goal_id: str) -> dict:
    """Profundidade declarada × validada por dimensão — só de tentativas
    BEM-SUCEDIDAS em itens que pertenceram a projeções deste objetivo."""
    goal = get_goal(settings, goal_id)
    cog = _cog(settings)
    pages = set()
    for r in cog.execute("SELECT working_set FROM cognitive_projections "
                         "WHERE goal_id=?", (goal_id,)):
        ws = json.loads(r["working_set"])
        pages |= {i["page"] for i in ws["items"]}
    rows = cog.execute(
        "SELECT item, exercise FROM retrieval_attempts WHERE result='success'"
    ).fetchall()
    level_by_item = {r["item"]: r["level"] for r in
                     cog.execute("SELECT item, level FROM accessibility")}
    cog.close()
    evidence = [{"exercise": r["exercise"],
                 "level": level_by_item.get(r["item"], "none")}
                for r in rows if r["item"] in pages]
    return {"goal_id": goal_id, "title": goal["title"],
            "depth": depth_progress(goal["depth_desired"], evidence),
            "evidence_n": len(evidence)}


def curation_projection(settings: Settings, limit: int = 20) -> dict:
    """CurationProjection (§5.11): prioriza o trabalho de curadoria SOB
    a ótica cognitiva (alinhamento com objetivos ativos) — leitura pura,
    zero escrita no canônico."""
    cog = _cog(settings)
    focus_pages: set = set()
    for r in cog.execute("SELECT goal FROM focus_goals WHERE status='active'"):
        goal = json.loads(r["goal"])
        focus_pages.add(goal["root"])
        focus_pages |= set(goal.get("pinned", []))
    cog.close()
    idx = connect(settings.app_support / "index.db")
    contested = {r["page"] for r in idx.execute(
        "SELECT page FROM page_overlay WHERE status='low_yield'")}
    idx.close()
    items = []
    reader = BundleReader(settings.path("knowledge") / "bundle")
    for doc in reader.iter_concepts():
        meta = doc.meta.model_dump(exclude_none=True)
        signals = []
        if meta.get("stale_as_of"):
            signals.append(("stale", 0.6))
        if doc.rel_path in contested:
            signals.append(("contested", 0.8))
        if doc.meta.type == "question":
            signals.append(("question", 0.7))
        if not signals:
            continue
        aligned = doc.rel_path in focus_pages
        score = max(w for _, w in signals) + (0.3 if aligned else 0.0)
        items.append({"page": doc.rel_path,
                      "signals": [s for s, _ in signals],
                      "aligned_with_focus": aligned,
                      "score": round(score, 2),
                      "reason": " + ".join(s for s, _ in signals)
                      + (" · alinhada a um objetivo ativo" if aligned
                         else "")})
    items.sort(key=lambda i: (-i["score"], i["page"]))
    return {"items": items[:limit], "considered": len(items)}


def cognitive_metrics(settings: Settings) -> dict:
    """Métricas §17.2/17.3 — computadas dos dados, nomeadas, sem rótulo."""
    cog = _cog(settings)
    attempts = [dict(r) for r in cog.execute(
        "SELECT item, exercise, confidence_before, result, created_at "
        "FROM retrieval_attempts ORDER BY created_at")]
    reviews = cog.execute("SELECT status, COUNT(*) c FROM review_schedules "
                          "GROUP BY status").fetchall()
    sessions = [dict(r) for r in cog.execute(
        "SELECT session FROM cognitive_sessions")]
    cog.close()
    pairs = [(a["confidence_before"], 1 if a["result"] == "success" else 0)
             for a in attempts]
    seen: dict[str, float] = {}
    delayed = []
    for a in attempts:                       # recall com ≥1 dia de intervalo
        if a["item"] in seen and a["created_at"] - seen[a["item"]] >= 86400:
            delayed.append(1 if a["result"] == "success" else 0)
        seen[a["item"]] = a["created_at"]
    apply_like = [a for a in attempts
                  if a["exercise"] in ("apply", "transfer")]
    fails: dict[str, int] = {}
    for a in attempts:
        if a["result"] == "failure":
            fails[a["item"]] = fails.get(a["item"], 0) + 1
    review_counts = {r["status"]: r["c"] for r in reviews}
    latencies = []
    for s in sessions:
        data = json.loads(s["session"])
        if data.get("resumed_at") and data.get("suspended_at"):
            latencies.append(data["resumed_at"] - data["suspended_at"])
    def _rate(xs):
        return round(sum(xs) / len(xs), 3) if xs else None
    return {
        "attempts": len(attempts),
        "brier": brier_score(pairs),
        "delayed_recall_rate": _rate(delayed),
        "application_success_rate": _rate(
            [1 if a["result"] == "success" else 0 for a in apply_like]),
        "error_recurrence_items": sorted(
            i for i, n in fails.items() if n >= 2),
        "review_completion": {
            "done": review_counts.get("done", 0),
            "due": review_counts.get("due", 0),
            "cancelled": review_counts.get("cancelled", 0)},
        "resumption_latency_s": _rate(latencies),
        "sessions": {"total": len(sessions)},
    }


class ReportMetacognitiveExperience(UseCase):
    """Experiência DECLARADA (Efklides): evento revisável, não diagnóstico."""

    def __init__(self, settings: Settings, body: dict, notify=None):
        self._settings = settings
        self._body = body
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        kind = self._body.get("type")
        if kind not in EXPERIENCE_TYPES:
            raise ValueError(f"type ∈ {EXPERIENCE_TYPES}")
        intensity = int(self._body.get("intensity", 3))
        if not 1 <= intensity <= 5:
            raise ValueError("intensity: escala 1..5")
        cog = _cog(self._settings)
        cur = cog.execute(
            "INSERT INTO metacog_experiences(session_id, item, type, "
            "intensity, note) VALUES (?,?,?,?,?)",
            (self._body.get("session_id"), self._body.get("item"),
             kind, intensity, self._body.get("note")))
        cog.commit()
        experience_id = cur.lastrowid
        cog.close()
        self._notify("metacognitive.experience.reported",
                     {"type": kind, "intensity": intensity})
        return {"id": experience_id, "type": kind, "intensity": intensity}


class RegisterAnalogy(UseCase):
    """Analogia estruturada — recusa sem pontos de ruptura declarados."""

    def __init__(self, settings: Settings, body: dict, notify=None):
        self._settings = settings
        self._body = body
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        analogy = new_analogy(
            analogy_id=_FOCUS_IDS.next_rendered(),
            source=self._body.get("source", ""),
            target=self._body.get("target", ""),
            mappings=self._body.get("mappings", []),
            preserved=self._body.get("preserved"),
            breaks=self._body.get("breaks"),
            didactic_goal=self._body.get("didactic_goal", ""),
            origin=self._body.get("origin", "human"))
        cog = _cog(self._settings)
        cog.execute("INSERT INTO analogies(id, analogy) VALUES (?,?)",
                    (analogy["id"], json.dumps(analogy)))
        cog.commit()
        cog.close()
        self._notify("analogy.registered", {"id": analogy["id"]})
        return analogy


def list_analogies(settings: Settings) -> list[dict]:
    cog = _cog(settings)
    rows = cog.execute("SELECT analogy, status, feedback_score FROM "
                       "analogies ORDER BY created_at DESC LIMIT 50")
    out = [{**json.loads(r["analogy"]), "status": r["status"],
            "feedback_score": r["feedback_score"]} for r in rows]
    cog.close()
    return out


class PromoteAnalogy(UseCase):
    """Gate humano: a analogia SÓ vira memória canônica por gesto
    explícito — via o MESMO PromoteToMemory de sempre (sanduíche e
    lint inclusos), com os limites SEMPRE no corpo."""

    def __init__(self, settings: Settings, analogy_id: str, notify=None):
        self._settings = settings
        self._analogy_id = analogy_id
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        cog = _cog(self._settings)
        row = cog.execute("SELECT analogy FROM analogies WHERE id=? AND "
                          "status IN ('draft','kept')",
                          (self._analogy_id,)).fetchone()
        cog.close()
        if not row:
            raise KeyError(f"analogia {self._analogy_id}")
        a = json.loads(row["analogy"])
        body = (f"Analogia entre **{a['source']}** e **{a['target']}**"
                f" ({a['didactic_goal'] or 'didática'}).\n\n"
                "## Correspondências\n"
                + "\n".join(f"- {m}" for m in a["mappings"])
                + ("\n\n## Relações preservadas\n"
                   + "\n".join(f"- {p}" for p in a["preserved"])
                   if a["preserved"] else "")
                + "\n\n## Onde a analogia QUEBRA\n"
                + "\n".join(f"- {b}" for b in a["breaks"])
                + "\n\nNão é equivalência exata.")
        from .promote_memory import PromoteToMemory
        result = PromoteToMemory(
            self._settings, kind="semantic",
            title=f"Analogia: {a['source']} ↔ {a['target']}",
            content=body, source="cognitive:analogy",
            privacy="local_only",
            tags=["analogia"]).execute()
        cog = _cog(self._settings)
        cog.execute("UPDATE analogies SET status='promoted', "
                    "updated_at=unixepoch('subsec') WHERE id=?",
                    (self._analogy_id,))
        cog.commit()
        cog.close()
        self._notify("analogy.promoted", {"id": self._analogy_id,
                                          "page": result["pages"][0]})
        return {"analogy_id": self._analogy_id, "page": result["pages"][0]}


def prompt_for(settings: Settings, exercise: str, title: str,
               item: str | None = None) -> dict:
    """Prompt determinístico + scaffolding com fading: o nível de
    apoio vem da sequência de recuperações do item (streak)."""
    streak = 0
    if item:
        cog = _cog(settings)
        row = cog.execute("SELECT streak FROM accessibility WHERE item=?",
                          (item,)).fetchone()
        cog.close()
        streak = row["streak"] if row else 0
    return {"exercise": exercise,
            "prompt": exercise_prompt(exercise, title),
            "support": support_level(streak)}


def episodes(settings: Settings, limit: int = 40) -> list[dict]:
    """Memória EPISÓDICA da experiência (Tulving): a linha do tempo de
    passos/tentativas por sessão — contextual, datada, nunca promovida
    automaticamente a conhecimento semântico (CLS)."""
    cog = _cog(settings)
    rows = cog.execute(
        "SELECT id, goal_id, state, session, started_at "
        "FROM cognitive_sessions ORDER BY started_at DESC LIMIT 12"
    ).fetchall()
    cog.close()
    out = []
    for r in rows:
        data = json.loads(r["session"])
        for step in data.get("steps", [])[-limit:]:
            out.append({"session_id": r["id"], "goal_id": r["goal_id"],
                        "at": step.get("at"), "kind": step.get("kind"),
                        "item": step.get("item"),
                        "note": step.get("note")})
    out.sort(key=lambda e: -(e["at"] or 0))
    return out[:limit]
