"""API do daemon (Parte V §8 + v0.6 §5.4 + patch v0.7 §5.2).

Auth: token efêmero gravado no handshake (app_support/daemon.json),
aceito por header `x-llmwiki-auth` OU query `?auth=` — o `?auth=` existe
porque EventSource não envia headers customizados.
"""
from __future__ import annotations
import asyncio
import json
import secrets
import time
from fastapi import FastAPI, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from ..facades import MemoryFacade
from ..runtime.events import EventBus
from ..runtime.governor import Governor
from ..runtime.queue import JobQueue
from ..settings import Settings


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
    app = FastAPI(title="llmwiki", version="0.7.0")
    token = token or issue_token(s)

    def auth(request: Request) -> None:
        if request.headers.get("x-llmwiki-auth") == token:
            return
        if request.query_params.get("auth") == token:
            return
        raise HTTPException(401, "token inválido")

    from fastapi import Depends

    @app.get("/health")
    def health():
        return {"ok": True, "version": "0.7.0"}

    @app.get("/status", dependencies=[Depends(auth)])
    def status():
        return {"pending_jobs": queue.pending_count(),
                "budget_left_usd": round(gov.budget_left(), 2),
                "spent_today_usd": round(gov.spent_today(), 4)}

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
    return app
