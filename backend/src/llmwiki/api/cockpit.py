from __future__ import annotations
import time
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from ..facades import (CognitionFacade, CompilerFacade, CurationFacade,
                       MemoryFacade)
from ..retrieval import observatory
from ..retrieval.related import related_pages
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
    compiler = CompilerFacade(s)
    compiler.seed_pipelines()          # builtin idempotentes (v0.17)
    curation.seed_reference()          # referência do mundo (v0.22)
    cognition = CognitionFacade(s)

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
        from .system import links
        return {"pages": len(pages), "chunks": chunks,
                "decisions": by_type.get("decision", 0),
                "stale": stale[:10], "stale_count": len(stale),
                "orphans": orphans[:10], "orphan_count": len(orphans),
                "pending_jobs": pending, "by_type": by_type,
                "budget_left_usd": round(gov.budget_left(), 2),
                "recommended_actions": actions,
                "_links": links(self="/cockpit/dashboard",
                                stats="/cockpit/stats", inbox="/cockpit/inbox",
                                memory="/cockpit/memory",
                                quality="/cockpit/quality",
                                insights="/cockpit/insights",
                                health="/health/full")}

    # ---------- Inbox de conhecimento (raw/ não compilado) ----------
    @app.get("/cockpit/inbox", dependencies=[Depends(auth)])
    def inbox():
        rt = connect(s.app_support / "runtime.db")
        cache = {r["source"]: (r["sha"], r["page"]) for r in
                 rt.execute("SELECT source, sha, page FROM compile_cache")}
        rt.close()
        import hashlib
        items = []
        raw = kb / "raw"
        for p in sorted(raw.rglob("*")):
            if p.suffix.lower() not in {".md", ".pdf", ".epub", ".txt"}:
                continue
            rel = str(p.relative_to(kb))
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            cached_sha, page = cache.get(rel, (None, None))
            stat = p.stat()
            items.append({"path": rel, "privacy": s.resolve_privacy(rel),
                          "bytes": stat.st_size,
                          "modified": time.strftime(
                              "%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                          "page": page,
                          "status": ("novo" if not cached_sha else
                                     "compilado" if cached_sha == sha
                                     else "stale")})
        return {"items": items}

    # ---------- Ingestão pelo app (v0.11): conteúdo → raw/ → pipeline ----
    @app.post("/cockpit/ingest", dependencies=[Depends(auth)])
    def ingest(body: dict):
        try:
            result = compiler.ingest(
                filename=body["filename"], content=body.get("content"),
                content_base64=body.get("content_base64"),
                subdir=body.get("subdir"))
        except (KeyError, ValueError) as e:
            raise HTTPException(400, str(e))
        if body.get("compile"):
            result["job_id"] = queue.enqueue(
                "compile_source", {"path": result["path"]}, priority=6)
        bus.emit("system", "source.ingested",
                 {"path": result["path"],
                  "job_id": result.get("job_id")})
        return result

    # ---------- Estatísticas para os gráficos do Dashboard (v0.11) ------
    @app.get("/cockpit/stats", dependencies=[Depends(auth)])
    def stats():
        pages = _pages()
        by_type: dict[str, int] = {}
        for p in pages:
            by_type[p["type"]] = by_type.get(p["type"], 0) + 1
        rt = connect(s.app_support / "runtime.db")
        heat = [0, 0, 0, 0, 0]                      # buckets de 0.2 em [0,1]
        for (score,) in rt.execute("SELECT score FROM page_heat"):
            heat[min(4, int((score or 0) / 0.2))] += 1
        outcomes = {r["verdict"]: r["c"] for r in rt.execute(
            "SELECT verdict, COUNT(*) c FROM ask_outcomes GROUP BY verdict")}
        per_day = [{"day": r["day"], "n": r["n"]} for r in rt.execute(
            "SELECT date(ts, 'unixepoch') day, COUNT(*) n FROM ask_outcomes "
            "WHERE ts > unixepoch() - 14*86400 GROUP BY day ORDER BY day")]
        rt.close()
        return {"by_type": sorted(by_type.items(), key=lambda kv: -kv[1]),
                "heat_buckets": heat,
                "outcomes": {v: outcomes.get(v, 0)
                             for v in ("useful", "dead_end", "corrected")},
                "outcomes_per_day": per_day}

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
        from .system import links
        return {"path": path, "body": d.body,
                "meta": d.meta.model_dump(exclude_none=True, mode="json"),
                "git": gitlog,
                "related": related_pages(s, path),   # A-mem: o link que falta
                "_links": links(self=f"/cockpit/page?path={path}",
                                stale="/cockpit/page/stale",
                                freeze="/cockpit/freeze",
                                collection="/cockpit/pages")}

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

    # ================================================= Fase 5 (v0.15)
    @app.get("/cockpit/graph", dependencies=[Depends(auth)])
    def graph():
        return observatory.graph_data(s)

    @app.get("/cockpit/insights", dependencies=[Depends(auth)])
    def insights():
        return observatory.insights(s)

    @app.get("/cockpit/dictionary", dependencies=[Depends(auth)])
    def dictionary():
        return observatory.dictionary(s)

    @app.get("/cockpit/traces", dependencies=[Depends(auth)])
    def traces():
        return {"traces": observatory.traces(s)}

    @app.get("/cockpit/trace", dependencies=[Depends(auth)])
    def trace(ask_id: str):
        return observatory.trace(s, ask_id)

    @app.get("/cockpit/tags", dependencies=[Depends(auth)])
    def tags():
        acc: dict[str, int] = {}
        for p in _pages():
            for t in p["tags"]:
                acc[t] = acc.get(t, 0) + 1
        return {"tags": sorted(acc.items(), key=lambda kv: -kv[1])}

    @app.post("/cockpit/tags", dependencies=[Depends(auth)])
    def tag_operation(body: dict):
        try:
            return curation.rename_tag(body["from"], body.get("to"))
        except (KeyError, ValueError) as e:
            raise HTTPException(400, str(e))

    from .system import links

    @app.get("/cockpit/config", dependencies=[Depends(auth)])
    def config_get():
        return {**s.snapshot(),
                "_links": links(self="/cockpit/config",
                                history="/cockpit/config/history",
                                rollback="/cockpit/config/rollback")}

    @app.post("/cockpit/config", dependencies=[Depends(auth)])
    def config_set(body: dict):
        """Ajuste versionado (v0.16): valida tipo/domínio, aplica a quente,
        grava no ring de 30 gerações; probe reprovado reverte sozinho."""
        try:
            result = curation.tune_config(body, notify=lambda t, d:
                                          bus.emit("system", t, d))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {**result["snapshot"],
                "history_id": result["history_id"],
                "trace_id": result["trace_id"],
                "_links": links(self="/cockpit/config",
                                history="/cockpit/config/history",
                                rollback="/cockpit/config/rollback")}

    @app.get("/cockpit/config/history", dependencies=[Depends(auth)])
    def config_hist(limit: int = 30):
        return {"history": curation.config_history(limit),
                "_links": links(self="/cockpit/config/history",
                                config="/cockpit/config",
                                rollback="/cockpit/config/rollback")}

    @app.post("/cockpit/config/rollback", dependencies=[Depends(auth)])
    def config_rollback():
        """Retorna à configuração ANTERIOR à vigente (nova geração no ring)."""
        try:
            result = curation.rollback_config(notify=lambda t, d:
                                              bus.emit("system", t, d))
        except ValueError as e:
            raise HTTPException(409, str(e))
        return {**result,
                "_links": links(self="/cockpit/config/rollback",
                                config="/cockpit/config",
                                history="/cockpit/config/history")}

    @app.get("/cockpit/behavior", dependencies=[Depends(auth)])
    def behavior():
        rt = connect(s.app_support / "runtime.db")
        weights = {r["stream"]: r["weight"] for r in rt.execute(
            "SELECT stream, weight FROM stream_weights")}
        rt.close()
        adapters = s.path("adapters") / "ACTIVE"
        return {"stream_weights": weights,
                "flags": dict(s.flags),
                "memory": dict(s.memory),
                "active_adapter": adapters.read_text().strip()
                                  if adapters.exists() else None,
                "eval": eval_results()["categories"]}

    @app.post("/cockpit/behavior/reset-streams", dependencies=[Depends(auth)])
    def reset_streams():
        rt = connect(s.app_support / "runtime.db")
        rt.execute("DELETE FROM stream_weights")
        rt.commit()
        rt.close()
        bus.emit("system", "behavior.streams_reset", {})
        return {"ok": True}

    @app.get("/cockpit/export", dependencies=[Depends(auth)])
    def export(format: str = "zip", include_local: bool = False,
               types: str = "", tag: str = ""):
        try:
            result = curation.export(
                format=format, include_local=include_local,
                types=[t for t in types.split(",") if t] or None,
                tag=tag or None)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return Response(
            content=result["content"], media_type=result["media_type"],
            headers={"Content-Disposition":
                     f'attachment; filename="{result["filename"]}"'})

    # ---------- Base fria (v0.12): congelar · reciclar · inspecionar ----
    @app.post("/cockpit/freeze", dependencies=[Depends(auth)])
    def freeze(body: dict):
        try:
            result = curation.freeze(body["path"],
                                     force=bool(body.get("force")),
                                     reason=body.get("reason", ""))
        except FileNotFoundError:
            raise HTTPException(404)
        except ValueError as e:              # FreezeVeto: gate reprovou
            raise HTTPException(409, str(e))
        bus.emit("system", "memory.frozen", {"page": result["page"]})
        return result

    @app.post("/cockpit/recycle", dependencies=[Depends(auth)])
    def recycle(body: dict):
        try:
            result = curation.recycle(body["path"])
        except KeyError as e:
            raise HTTPException(404, str(e))
        bus.emit("system", "memory.recycled", {"page": result["page"]})
        return result

    @app.get("/cockpit/cold", dependencies=[Depends(auth)])
    def cold():
        return curation.cold()

    # ---------- Camada cognitiva (v0.18) ----------
    @app.post("/cockpit/state", dependencies=[Depends(auth)])
    def declare_state(body: dict):
        """Estado contextual DECLARADO (CLT) — carga 1..5 obrigatória."""
        try:
            return cognition.declare_state(
                load=body["load"], focus=body.get("focus"),
                energy=body.get("energy"),
                time_available_min=body.get("time_available_min"),
                note=body.get("note"),
                notify=lambda t, d: bus.emit("system", t, d))
        except (KeyError, ValueError, TypeError) as e:
            raise HTTPException(400, str(e))

    @app.get("/cockpit/cognition", dependencies=[Depends(auth)])
    def cognition_overview():
        from .system import links
        return {**cognition.overview(),
                "_links": links(self="/cockpit/cognition",
                                state="/cockpit/state",
                                observations="/cockpit/cognition/observations",
                                observe="/cockpit/cognition/observe",
                                attention="/cockpit/attention")}

    @app.post("/cockpit/cognition/observe", dependencies=[Depends(auth)])
    def cognition_observe():
        return cognition.observe(notify=lambda t, d: bus.emit("system", t, d))

    @app.get("/cockpit/cognition/observations", dependencies=[Depends(auth)])
    def cognition_observations(status: str = ""):
        return {"observations": cognition.observations(status or None)}

    @app.post("/cockpit/cognition/observations/review",
              dependencies=[Depends(auth)])
    def cognition_review(body: dict):
        """Gate humano: aceitar (aplica suggestion pela linhagem de
        config), rejeitar ou suspender uma observação."""
        try:
            return cognition.review_observation(
                body["id"], body["action"],
                notify=lambda t, d: bus.emit("system", t, d))
        except (KeyError, ValueError) as e:
            code = 404 if isinstance(e, KeyError) else 400
            raise HTTPException(code, str(e))

    @app.get("/cockpit/attention", dependencies=[Depends(auth)])
    def attention(minutes: int = 0):
        """Economia de atenção: o melhor investimento dos próximos N
        minutos, com o porquê de cada item."""
        return cognition.attention_plan(minutes or None)

    # ---------- Pipelines configuráveis (v0.17) ----------
    @app.get("/cockpit/pipelines", dependencies=[Depends(auth)])
    def pipelines_list():
        from .system import links
        return {"pipelines": compiler.pipelines(),
                "_links": links(self="/cockpit/pipelines",
                                runs="/cockpit/pipelines/runs",
                                run="/cockpit/pipelines/run")}

    @app.post("/cockpit/pipelines", dependencies=[Depends(auth)])
    def pipelines_save(body: dict):
        try:
            return compiler.save_pipeline(body["name"], body)
        except (KeyError, ValueError) as e:
            raise HTTPException(400, str(e))

    @app.delete("/cockpit/pipelines", dependencies=[Depends(auth)])
    def pipelines_delete(name: str):
        try:
            return compiler.delete_pipeline(name)
        except KeyError:
            raise HTTPException(404)

    @app.post("/cockpit/pipelines/run", dependencies=[Depends(auth)])
    def pipelines_run(body: dict):
        """Roda ASSÍNCRONO pela fila (job `pipeline`, slot heavy) — o
        filme sai por SSE (`pipeline.stage`) e fica em pipeline_runs."""
        if not any(p["name"] == body.get("name")
                   for p in compiler.pipelines()):
            raise HTTPException(404, f"pipeline desconhecido: {body.get('name')}")
        jid = queue.enqueue("pipeline", {"name": body["name"]}, priority=6)
        return {"job_id": jid, "pipeline": body["name"]}

    @app.get("/cockpit/pipelines/runs", dependencies=[Depends(auth)])
    def pipelines_runs(name: str = "", limit: int = 20):
        return {"runs": compiler.pipeline_runs(name or None, limit)}

    # ---------- Referência do mundo (v0.22) ----------
    @app.get("/cockpit/reference", dependencies=[Depends(auth)])
    def reference():
        return curation.reference_stats()

    @app.post("/cockpit/reference", dependencies=[Depends(auth)])
    def reference_import(body: dict):
        try:
            return curation.import_reference(
                body, notify=lambda t, d: bus.emit("system", t, d))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/cockpit/reference/check", dependencies=[Depends(auth)])
    def reference_check(body: dict):
        """Citação mal-atribuída: confere quote×autor contra a base
        determinística (anti-alucinação, irmão dos check-digits)."""
        return curation.check_quotation(body.get("text", ""),
                                        body.get("author"))

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
