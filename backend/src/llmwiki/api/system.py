"""API do daemon (Parte V §8 + v0.6 §5.4 + patch v0.7 §5.2).

Auth: token efêmero gravado no handshake (app_support/daemon.json),
aceito por header `x-llmwiki-auth` OU query `?auth=` — o `?auth=` existe
porque EventSource não envia headers customizados.
"""
from __future__ import annotations
import asyncio
import json
import os
import secrets
import sys
import threading
import time
from fastapi import FastAPI, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from ..facades import MemoryFacade
from ..kernel.identity import factory as id_factory, parse as parse_id
from ..runtime.db import connect
from ..runtime.events import EventBus
from ..runtime.governor import Governor
from ..runtime.queue import JobQueue
from ..settings import Settings

VERSION = "1.0.0"


def links(**rels: str) -> dict:
    """HATEOAS (RFC 8288 em espírito): todo recurso diz aonde se pode ir
    a partir dele — o cliente navega por relação, não por URL decorada."""
    return {rel: {"href": href} for rel, href in rels.items()}


def issue_token(s: Settings) -> str:
    """Gera o token da sessão e persiste o handshake para o app Electron."""
    token = secrets.token_urlsafe(24)
    handshake = s.app_support / "daemon.json"
    handshake.write_text(json.dumps({
        "port": s.server.get("port", 8377),
        "host": s.server.get("host", "127.0.0.1"),
        "token": token,
        "started_at": time.time()}))
    handshake.chmod(0o600)
    return token


def build_app(s: Settings, queue: JobQueue, gov: Governor,
              bus: EventBus, token: str | None = None) -> FastAPI:
    app = FastAPI(title="llmwiki", version=VERSION)
    token = token or issue_token(s)
    # identidade da INSTÂNCIA (v0.16): um snowflake por boot do daemon —
    # aparece em /, /health e /health/full; correlaciona spans entre boots
    instance_id = id_factory("daemon").next_rendered()
    started_at = time.time()

    def auth(request: Request) -> None:
        if request.headers.get("x-llmwiki-auth") == token:
            return
        if request.query_params.get("auth") == token:
            return
        raise HTTPException(401, "token inválido")

    from fastapi import Depends

    @app.get("/")
    def root():
        """Raiz HATEOAS: o mapa navegável do serviço. Sem auth — só
        relações e hrefs, nenhum dado."""
        return {"service": "llmwiki", "version": VERSION,
                "instance": instance_id,
                "_links": links(
                    self="/", health="/health", health_full="/health/full",
                    status="/status", jobs="/jobs", ask="/ask",
                    events="/events", dashboard="/cockpit/dashboard",
                    pages="/cockpit/pages", memory="/cockpit/memory",
                    config="/cockpit/config",
                    config_history="/cockpit/config/history",
                    config_rollback="/cockpit/config/rollback",
                    cold="/cockpit/cold", graph="/cockpit/graph",
                    insights="/cockpit/insights", export="/cockpit/export",
                    pipelines="/cockpit/pipelines",
                    pipeline_runs="/cockpit/pipelines/runs",
                    cognition="/cockpit/cognition",
                    state="/cockpit/state",
                    attention="/cockpit/attention",
                    focus_goals="/cognitive/goals",
                    projections="/cognitive/projections",
                    sessions="/cognitive/sessions",
                    reviews_due="/cognitive/reviews/due")}

    @app.get("/health")
    def health():
        return {"ok": True, "version": VERSION, "instance": instance_id,
                "_links": links(self="/health", full="/health/full")}

    @app.get("/health/full", dependencies=[Depends(auth)])
    def health_full():
        """Saúde PROFUNDA (v0.16): instância, processo, fila, stacks de
        dados (um bloco por banco — cada natureza de informação tem o seu),
        barramento e recursos da máquina."""
        import resource
        import shutil
        usage = resource.getrusage(resource.RUSAGE_SELF)
        stacks = {}
        for name in ("runtime.db", "index.db", "cold.db"):
            path = s.app_support / name
            if not path.exists():
                stacks[name] = {"present": False}
                continue
            conn = connect(path)
            wal = path.with_name(path.name + "-wal")
            stacks[name] = {
                "present": True,
                "bytes": path.stat().st_size,
                "wal_bytes": wal.stat().st_size if wal.exists() else 0,
                "integrity": conn.execute(
                    "PRAGMA quick_check(1)").fetchone()[0],
                "tables": {r["name"]: conn.execute(
                    f'SELECT COUNT(*) c FROM "{r["name"]}"').fetchone()["c"]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%' "
                        "AND name NOT LIKE '%_fts%'")},
            }
            conn.close()
        rt = connect(s.app_support / "runtime.db")
        queue_states = {r["state"]: r["c"] for r in rt.execute(
            "SELECT state, COUNT(*) c FROM jobs GROUP BY state")}
        oldest = rt.execute("SELECT MIN(created_at) t FROM jobs "
                            "WHERE state='queued'").fetchone()["t"]
        config_rows = rt.execute(
            "SELECT COUNT(*) c, MAX(trace_id) latest "
            "FROM config_history").fetchone()
        rt.close()
        disk = shutil.disk_usage(s.home.expanduser())
        return {
            "ok": True,
            "instance": {"id": instance_id, **parse_id(instance_id),
                         "version": VERSION, "pid": os.getpid(),
                         "python": sys.version.split()[0],
                         "uptime_s": round(time.time() - started_at, 1)},
            "process": {"rss_mb": round(usage.ru_maxrss / 1024, 1),
                        "cpu_user_s": round(usage.ru_utime, 2),
                        "threads": threading.active_count()},
            "queue": {"by_state": queue_states,
                      "oldest_queued_age_s":
                          round(time.time() - oldest, 1) if oldest else None},
            "stacks": stacks,
            "bus": {"subscribers": bus.subscriber_count()},
            "config": {"history_entries": config_rows["c"],
                       "current_trace": config_rows["latest"]},
            "resources": {"disk_free_mb": disk.free // 2**20,
                          "disk_used_pct":
                              round(100 * disk.used / disk.total, 1)},
            "budget": {"left_usd": round(gov.budget_left(), 2),
                       "spent_today_usd": round(gov.spent_today(), 4)},
            "_links": links(self="/health/full", status="/status",
                            jobs="/jobs", config="/cockpit/config")}

    @app.get("/status", dependencies=[Depends(auth)])
    def status():
        return {"pending_jobs": queue.pending_count(),
                "budget_left_usd": round(gov.budget_left(), 2),
                "spent_today_usd": round(gov.spent_today(), 4),
                "instance": instance_id,
                "_links": links(self="/status", health="/health/full",
                                jobs="/jobs", events="/events")}

    @app.get("/jobs", dependencies=[Depends(auth)])
    def jobs(limit: int = 50):
        return {"jobs": queue.list(limit)}

    @app.post("/jobs", dependencies=[Depends(auth)])
    def enqueue(body: dict):
        jid = queue.enqueue(body["type"], body.get("payload", {}),
                            priority=body.get("priority", 5),
                            dedupe_key=body.get("dedupe_key"))
        return {"job_id": jid}

    @app.post("/ask", dependencies=[Depends(auth)])
    def ask(body: dict):
        return MemoryFacade(s, gov).ask(
            body["query"], deep=body.get("deep", False),
            local_only=body.get("local_only", False),
            as_of=body.get("as_of"))

    @app.get("/events", dependencies=[Depends(auth)])
    async def events(request: Request):
        q = bus.subscribe()

        async def gen():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.to_thread(q.get, True, 15.0)
                        yield {"event": event["type"],
                               "data": json.dumps(event, default=str)}
                    except Exception:
                        yield {"event": "ping", "data": "{}"}
            finally:
                bus.unsubscribe(q)

        return EventSourceResponse(gen())

    from .cockpit import mount_cockpit
    mount_cockpit(app, s, queue, gov, bus, auth)
    from .cognitive import mount_cognitive
    mount_cognitive(app, s, bus, auth)
    return app
