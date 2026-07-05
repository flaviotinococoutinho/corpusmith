from __future__ import annotations
import time
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from ..facades import CurationFacade, MemoryFacade
from ..settings import Settings
from ..runtime.db import connect
from ..okf.writer import BundleWriter

SEMANTIC_TYPES = {"concept", "academic_paper", "decision",
                  "schema_specification", "field_profile", "learning_note"}
PROCEDURAL_TYPES = {"runbook", "skill"}

def mount_cockpit(app: FastAPI, s: Settings, queue, gov, bus, auth) -> None:
    kb = s.path("knowledge")
    curation = CurationFacade(s)
    memory_facade = MemoryFacade(s)

    def writer() -> BundleWriter:
        return BundleWriter(kb)

    def _pages() -> list[dict]:
        w = writer()
        out = []
        for d in w.reader.iter_concepts():
            x = d.meta.model_dump(exclude_none=True, mode="json")
            out.append({"path": d.rel_path, "type": d.meta.type,
                        "title": d.meta.title or Path(d.rel_path).stem,
                        "description": d.meta.description,
                        "privacy": x.get("privacy"),
                        "stale": bool(x.get("stale_as_of")),
                        "confidence": x.get("confidence"),
                        "tags": d.meta.tags})
        return out

    def _orphans(pages: list[dict]) -> list[str]:
        idx = connect(s.app_support / "index.db")
        linked = {r["dst"] for r in idx.execute(
            "SELECT DISTINCT dst FROM graph_edges WHERE kind='wikilink'")}
        idx.close()
        return [p["path"] for p in pages if p["path"] not in linked]

    # ---------- Dashboard (tela inicial: estado da memória) ----------
    @app.get("/cockpit/dashboard", dependencies=[Depends(auth)])
    def dashboard():
        pages = _pages()
        orphans = _orphans(pages)
        stale = [p["path"] for p in pages if p["stale"]]
        idx = connect(s.app_support / "index.db")
        chunks = idx.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
        idx.close()
        rt = connect(s.app_support / "runtime.db")
        pending = rt.execute("SELECT COUNT(*) c FROM jobs WHERE state IN "
                             "('queued','leased')").fetchone()["c"]
        rt.close()
        by_type: dict[str, int] = {}
        for p in pages:
            by_type[p["type"]] = by_type.get(p["type"], 0) + 1
        actions = []
        if stale:
            actions.append(f"Revisar {len(stale)} página(s) stale")
        if orphans:
            actions.append(f"Linkar {len(orphans)} conceito(s) órfão(s)")
        if pending:
            actions.append(f"Acompanhar {pending} job(s) pendente(s)")
        return {"pages": len(pages), "chunks": chunks,
                "decisions": by_type.get("decision", 0),
                "stale": stale[:10], "stale_count": len(stale),
                "orphans": orphans[:10], "orphan_count": len(orphans),
                "pending_jobs": pending, "by_type": by_type,
                "budget_left_usd": round(gov.budget_left(), 2),
                "recommended_actions": actions}

    # ---------- Inbox de conhecimento (raw/ não compilado) ----------
    @app.get("/cockpit/inbox", dependencies=[Depends(auth)])
    def inbox():
        rt = connect(s.app_support / "runtime.db")
        rt.execute("CREATE TABLE IF NOT EXISTS compile_cache("
                   "source TEXT PRIMARY KEY, sha TEXT, at REAL)")
        cache = {r["source"]: r["sha"] for r in
                 rt.execute("SELECT source, sha FROM compile_cache")}
        rt.close()
        import hashlib
        items = []
        raw = kb / "raw"
        for p in sorted(raw.rglob("*")):
            if p.suffix.lower() not in {".md", ".pdf", ".epub", ".txt"}:
                continue
            rel = str(p.relative_to(kb))
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            cached = cache.get(rel)
            items.append({"path": rel, "privacy": s.resolve_privacy(rel),
                          "status": ("novo" if not cached else
                                     "compilado" if cached == sha else "stale")})
        return {"items": items}

    # ---------- Explorador OKF ----------
    @app.get("/cockpit/pages", dependencies=[Depends(auth)])
    def pages():
        return {"pages": _pages()}

    @app.get("/cockpit/page", dependencies=[Depends(auth)])
    def page(path: str):
        w = writer()
        if not w.reader.exists(path):
            raise HTTPException(404)
        d = w.reader.load(path)
        import subprocess
        gitlog = subprocess.run(
            ["git", "-C", str(kb), "log", "-5", "--format=%h %ad %s",
             "--date=short", "--", f"bundle/{path}"],
            capture_output=True, text=True).stdout.splitlines()
        return {"path": path, "body": d.body,
                "meta": d.meta.model_dump(exclude_none=True, mode="json"),
                "git": gitlog}

    @app.post("/cockpit/page/stale", dependencies=[Depends(auth)])
    def mark_stale(body: dict):
        if not writer().reader.exists(body["path"]):
            raise HTTPException(404)
        return curation.mark_stale(body["path"])

    # ---------- Chat/ask já existe (/ask) — aqui só o custo da sessão ----
    @app.get("/cockpit/ledger/today", dependencies=[Depends(auth)])
    def ledger_today():
        rt = connect(s.app_support / "runtime.db")
        row = rt.execute("SELECT COALESCE(SUM(usd),0) usd, COUNT(*) calls "
                         "FROM ledger WHERE ts > strftime('%s','now','start of day')"
                         ).fetchone()
        rt.close()
        return {"usd_today": round(row["usd"], 4), "calls": row["calls"]}

    # ---------- Promover para memória (o botão diferenciado) ----------
    @app.post("/cockpit/promote", dependencies=[Depends(auth)])
    def promote(body: dict):
        try:
            result = curation.promote(
                kind=body.get("kind", "semantic"), title=body["title"],
                content=body["content"], source=body.get("source", "chat"),
                privacy=body.get("privacy", "local_only"),
                description=body.get("description"),
                tags=body.get("tags", []))
        except ValueError as e:
            raise HTTPException(400, str(e))
        bus.emit("system", "memory.promoted",
                 {"kind": result["kind"], "page": result["pages"][0]})
        return result

    # ---------- Memória em 4 camadas ----------
    @app.get("/cockpit/memory", dependencies=[Depends(auth)])
    def memory():
        pages = _pages()
        rt = connect(s.app_support / "runtime.db")
        working = [dict(r) for r in rt.execute(
            "SELECT seq, channel, type, data, created_at FROM events "
            "ORDER BY seq DESC LIMIT 30")]
        rt.close()
        episodic = []
        log = kb / "bundle" / "log.md"
        if log.exists():
            episodic = [l for l in log.read_text().splitlines()
                        if l.startswith(("## ", "* "))][:60]
        adapters = s.path("adapters") / "ACTIVE"
        return {
            "working": working,
            "episodic": episodic,
            "semantic": [p for p in pages if p["type"] in SEMANTIC_TYPES],
            "procedural": {
                "pages": [p for p in pages if p["type"] in PROCEDURAL_TYPES],
                "active_adapter": adapters.read_text().strip()
                                   if adapters.exists() else None}}

    # ---------- Qualidade epistêmica ----------
    @app.get("/cockpit/quality", dependencies=[Depends(auth)])
    def quality(mode: str = "write"):
        findings = curation.lint(mode)          # mesma fonte do CLI okf lint
        pages = _pages()
        idx = connect(s.app_support / "index.db")
        bridges = [dict(r) for r in idx.execute(
            "SELECT src, dst, weight, small_side, large_side "
            "FROM graph_bridges ORDER BY weight LIMIT 10")]
        idx.close()
        return {"eval": eval_results()["categories"],
                "findings": findings.to_dicts(),
                "errors": findings.count("error"),
                "warnings": findings.count("warn"),
                "bridges": bridges,             # pontes frágeis (topologia)
                "orphan_count": len(_orphans(pages)),
                "stale_count": sum(p["stale"] for p in pages),
                "privacy_coverage": round(100 * sum(
                    1 for p in pages if p["privacy"]) / max(1, len(pages))),
                "pages": len(pages)}

    # ---------- Desfechos de consulta (v0.8 §8/§11) ----------
    @app.post("/cockpit/outcome", dependencies=[Depends(auth)])
    def outcome(body: dict):
        try:
            return memory_facade.record_outcome(
                verdict=body.get("verdict"), ask_id=body.get("ask_id"),
                note=body.get("note"), pages=body.get("pages", []))
        except ValueError as e:
            raise HTTPException(400, str(e))

    # ---------- Eval de memória (v0.8 §10) ----------
    @app.get("/cockpit/eval", dependencies=[Depends(auth)])
    def eval_results():
        rt = connect(s.app_support / "runtime.db")
        rows = rt.execute(
            "SELECT category, total, passed FROM eval_runs e "
            "WHERE ts = (SELECT MAX(ts) FROM eval_runs "
            "            WHERE category = e.category) "
            "GROUP BY category").fetchall()
        rt.close()
        return {"categories": [{"category": r["category"], "total": r["total"],
                                "passed": r["passed"]} for r in rows]}

    # ---------- Controle de autoridade (v0.8 §4) ----------
    @app.get("/cockpit/authorities", dependencies=[Depends(auth)])
    def authorities():
        idx = connect(s.app_support / "index.db")
        rows = idx.execute(
            "SELECT e.canonical, e.kind, e.qid, COUNT(DISTINCT pe.page) uses "
            "FROM entities e LEFT JOIN page_entities pe ON pe.entity_id = e.id "
            "GROUP BY e.id ORDER BY uses DESC LIMIT 500").fetchall()
        idx.close()
        return {"entities": [{"canonical": r["canonical"], "kind": r["kind"],
                              "qid": r["qid"], "uses": r["uses"]}
                             for r in rows]}

    # ---------- Candidatos do reflect (Dashboard, v0.8 §8) ----------
    @app.get("/cockpit/reflect", dependencies=[Depends(auth)])
    def reflect_candidates():
        return curation.reflect_candidates()

    # ---------- Revisão semanal assistida ----------
    @app.get("/cockpit/review", dependencies=[Depends(auth)])
    def review_current():
        return curation.weekly_review()

    @app.post("/cockpit/review/commit", dependencies=[Depends(auth)])
    def review_commit():
        jid = queue.enqueue("review_weekly", {}, priority=6,
                            dedupe_key=f"review:{time.strftime('%Y-W%W')}")
        return {"job_id": jid}
