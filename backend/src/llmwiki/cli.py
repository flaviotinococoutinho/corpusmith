"""CLI (Manual Ap. A + `okf lint/index` v0.6 §6).

Comandos offline (lint, index, bootstrap) falam direto com o bundle;
comandos de controle (status, jobs, ask, enqueue) falam com o daemon via
handshake (app_support/daemon.json). `llmwiki okf lint` usa EXATAMENTE a
mesma fonte do painel Qualidade: HarnessRunner.lint_bundle.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import httpx
from .facades import CompilerFacade, CurationFacade
from .okf.bootstrap import ensure_bundle
from .settings import Settings


def _handshake(s: Settings) -> dict:
    hs = s.app_support / "daemon.json"
    if not hs.exists():
        sys.exit("daemon não está rodando (handshake ausente); "
                 "suba com `just daemon`")
    return json.loads(hs.read_text())


def _client(s: Settings) -> tuple[str, dict]:
    h = _handshake(s)
    return (f"http://{h.get('host', '127.0.0.1')}:{h['port']}",
            {"x-llmwiki-auth": h["token"]})


def cmd_lint(s: Settings, args) -> int:
    findings = CurationFacade(s).lint(args.mode)   # mesma fonte do painel
    for f in findings:
        layer = "OKF" if f.okf_conformance else "política"
        print(f"{f.severity:5s} [{layer}] {f.rule:32s} {f.path}: {f.message}")
    errors = findings.count("error")
    print(f"\n{len(findings)} finding(s), {errors} erro(s)")
    return 1 if errors else 0


def cmd_index(s: Settings, args) -> int:
    print(json.dumps(CompilerFacade(s).rebuild_index()))
    return 0


def cmd_bootstrap(s: Settings, args) -> int:
    created = ensure_bundle(s.path("knowledge"))
    print("bundle criado" if created else "bundle já existia")
    return 0


def cmd_status(s: Settings, args) -> int:
    base, headers = _client(s)
    r = httpx.get(base + "/status", headers=headers, timeout=10)
    print(json.dumps(r.json(), indent=2))
    return 0


def cmd_jobs(s: Settings, args) -> int:
    base, headers = _client(s)
    r = httpx.get(base + "/jobs", headers=headers, timeout=10)
    for j in r.json()["jobs"]:
        print(f"{j['id']}  {j['state']:7s} p{j['priority']}  {j['type']}"
              + (f"  ERR {j['error'][:60]}" if j.get("error") else ""))
    return 0


def cmd_enqueue(s: Settings, args) -> int:
    base, headers = _client(s)
    r = httpx.post(base + "/jobs", headers=headers, timeout=10,
                   json={"type": args.type,
                         "payload": json.loads(args.payload)})
    print(json.dumps(r.json()))
    return 0


def cmd_ask(s: Settings, args) -> int:
    base, headers = _client(s)
    r = httpx.post(base + "/ask", headers=headers, timeout=300,
                   json={"query": args.query, "deep": args.deep,
                         "local_only": args.local})
    data = r.json()
    if data.get("abstained"):
        print("🤷 sem cobertura na base — abstenção "
              f"({'; '.join(data.get('gaps', []))})", file=sys.stderr)
        for m in data.get("cold_matches", []):
            print(f"  ❄️ fria compatível: {m['page']} "
                  f"(llmwiki recycle {m['page']})", file=sys.stderr)
        return 1
    if data.get("blocked"):
        print("⛔ resposta bloqueada pelo Harness (citações)", file=sys.stderr)
    print(data["answer"])
    uncertainty = data.get("uncertainty", 0)
    tail = f"[via {data['via']}]"
    if uncertainty > 0.85:
        tail += f" ~ incerta ({uncertainty:.0%})"
    print(f"\n{tail}", file=sys.stderr)
    return 0


def cmd_cold(s: Settings, args) -> int:
    stats = CurationFacade(s).cold()
    print(f"❄️ {stats['count']} memória(s) · {stats['compression_saved']}% "
          f"compactado · {stats['recycles']} reciclagem(ns)")
    for e in stats["entries"]:
        print(f"  {e['page']}  P(recall)={e['recall_p'] or 0:.3f}  "
              f"{e['packed']/1024:.1f}/{e['body_bytes']/1024:.1f} kB")
    return 0


def cmd_freeze(s: Settings, args) -> int:
    result = CurationFacade(s).freeze(args.page, force=args.force)
    print(f"🧊 congelada: {result['page']} "
          f"(P(recall)={result['recall_p']:.3f})")
    return 0


def cmd_recycle(s: Settings, args) -> int:
    result = CurationFacade(s).recycle(args.page)
    print(f"♻️ reciclada: {result['page']} ({result['times']}ª vez)")
    return 0


def cmd_daemon(s: Settings, args) -> int:
    from .daemon import main as daemon_main
    daemon_main()
    return 0


def cmd_seed(s: Settings, args) -> int:
    """Migração de dados PRÉ-DEFINIDOS (v1.0): referência do mundo
    (db/seeds/reference_seed.json ou --file) + pipelines builtin +
    golden eval (v1.6.3, QA-1 — o eval funciona out-of-the-box).
    Idempotente — nunca sobrescreve dado do usuário."""
    import json as _json
    from pathlib import Path as _P
    from .usecases.manage_reference import ImportReferenceData, seed_reference
    from .usecases.run_pipeline import seed_default_pipelines
    from .usecases.seed_eval import seed_golden_eval
    seed_reference(s)
    seed_default_pipelines(s)
    path = _P(args.file) if getattr(args, "file", None) else \
        _P(__file__).resolve().parent.parent.parent / "db" / "seeds" / \
        "reference_seed.json"
    counts = {}
    if path.is_file():
        counts = ImportReferenceData(
            s, _json.loads(path.read_text()), replace=False).execute()
    eval_counts = seed_golden_eval(s)
    print(f"seed ok: {counts or 'builtin apenas'} (+pipelines; "
          f"golden eval: {eval_counts})")
    return 0


def cmd_doctor(s: Settings, args) -> int:
    """Verifica invariantes (INV-001/002/003 + pipelines + cognitivo);
    --repair reconstrói o índice (nunca toca o canônico)."""
    import json as _json
    from .usecases.diagnose import DiagnoseSystem
    from .jobs import REGISTRY
    result = DiagnoseSystem(s, repair=args.repair,
                            known_jobs=set(REGISTRY)).execute()
    print(_json.dumps(result, indent=1, default=str))
    return 0 if result["ok"] else 2


def cmd_checkpoints(s: Settings, args) -> int:
    """A cadeia de derivações e o estado de cada uma.

    Torna inspecionável o que antes era carimbo espalhado: de qual estado da
    FONTE cada derivação veio, e se a cadeia acima dela se moveu."""
    import json as _json
    from .kernel.checkpoints import DERIVATIONS
    from .runtime.checkpoints import load, verify
    cps = load(s)
    linhas = []
    for v in verify(s):
        cp = cps.get(v.derivation)
        linhas.append({
            "derivation": v.derivation,
            "source": DERIVATIONS.get(v.derivation) or "(autoridade)",
            "state": v.state,
            "reason": v.reason,
            "input_state": cp.input_state[:12] if cp else None,
            "computed_at": cp.computed_at if cp else None,
            "detail": _json.loads(cp.detail) if cp and cp.detail else None})
    print(_json.dumps({"chain": linhas,
                       "stale": [x["derivation"] for x in linhas
                                 if x["state"].startswith("stale")]},
                      indent=1, default=str))
    return 1 if any(x["state"].startswith("stale") for x in linhas) else 0


def cmd_themes(s: Settings, args) -> int:
    """Temas com identidade e a última época de cada (RFC-001 §9).

    Torna o casamento INSPECIONÁVEL: sem isto, `theme_id`, evento e Jaccard
    ficariam só na tabela, e uma heurística no caminho de escrita que ninguém
    pode auditar é pior que nenhuma."""
    import json as _json
    from .runtime.db import connect
    idx = connect(s.app_support / "index.db")
    try:
        temas = [dict(r) for r in idx.execute(
            "SELECT theme_id, rel_path, born_at, died_at, members "
            "FROM themes ORDER BY died_at IS NOT NULL, born_at")]
        epocas = {}
        for r in idx.execute(
                "SELECT theme_id, event, at, jaccard, related FROM theme_epochs "
                "ORDER BY id"):
            epocas[r["theme_id"]] = dict(r)
    finally:
        idx.close()
    for tm in temas:
        tm["members"] = _json.loads(tm["members"])
        tm["vivo"] = tm.pop("died_at") is None
        ultima = epocas.get(tm["theme_id"])
        if ultima:
            ultima["related"] = _json.loads(ultima.get("related") or "[]")
        tm["ultima_epoca"] = ultima
    print(_json.dumps({"temas": temas, "total": len(temas),
                       "vivos": sum(1 for x in temas if x["vivo"])},
                      indent=1, default=str))
    return 0 if temas else 1


def cmd_curate(s: Settings, args) -> int:
    """curate <ato> [chave=valor ...] [--dry-run] — o ato humano no CLI.

    F1-PR1: até aqui suceder ou invalidar uma página só era possível
    editando o YAML à mão. `--dry-run` mostra diff, findings previstos e
    dependentes TMS sem tocar em nada."""
    import json as _json
    from .facades.curation_acts import CurationActsFacade
    from .harness.runner import HarnessRejection
    from .kernel.curation import UndoNotExpressible
    facade = CurationActsFacade(s)
    params: dict = {}
    for item in args.params:
        chave, _, valor = item.partition("=")
        if not _:
            print(f"parâmetro sem '=': {item}")
            return 2
        params[chave] = int(valor) if chave == "act_id" else valor
    try:
        if args.dry_run:
            result = facade.preview(args.act, params)
        else:
            result = facade.act(args.act, params)
    except KeyError as e:
        print(f"ato desconhecido ou inexistente: {e}; "
              f"atos disponíveis: {facade.kinds()}")
        return 2
    except HarnessRejection as e:
        print(_json.dumps({"rejeitado": str(e),
                           "findings": [f.__dict__ for f in e.findings]},
                          indent=1, ensure_ascii=False))
        return 1
    except UndoNotExpressible as e:
        # estado anterior não alcançável por escrita para a frente — recusa
        # NOMEADA, não traceback (AGENTS §9: erro com código estável)
        print(f"⛔ não é possível desfazer: {e}")
        return 3
    except (ValueError, FileNotFoundError) as e:
        print(f"⛔ {e}")
        return 2
    print(_json.dumps(result, indent=1, ensure_ascii=False, default=str))
    return 0


def cmd_backup(s: Settings, args) -> int:
    """backup create|verify|list|restore [--dry-run] [--force] [path]"""
    from .usecases.backup_restore import (CreateBackup, RestoreBackup,
                                          list_backups, verify_backup)
    import json as _json
    if args.op == "create":
        print(_json.dumps(CreateBackup(s, args.path).execute(), indent=1))
    elif args.op == "verify":
        # sem caminho ⇒ verifica o backup MAIS RECENTE (PR-0: `verify` sem
        # argumento estourava TypeError; o DoD do AGENTS.md §9 exige erro
        # com código estável, e "verificar o último" é o uso real no gate)
        archive = args.path
        if archive is None:
            existentes = [b for b in list_backups(s) if "error" not in b]
            if not existentes:
                print(_json.dumps({"ok": False,
                                   "error": "nenhum backup encontrado"},
                                  indent=1))
                return 1
            archive = existentes[-1]["path"]
        result = verify_backup(archive)
        print(_json.dumps(result, indent=1))
        return 0 if result["ok"] else 1
    elif args.op == "list":
        for b in list_backups(s):
            print(_json.dumps(b))
    elif args.op == "restore":
        result = RestoreBackup(s, args.path, dry_run=args.dry_run,
                               force=args.force).execute()
        print(_json.dumps(result, indent=1, default=str))
    return 0


def cmd_bench(s: Settings, args) -> int:
    """Delega ao harness versionado (llmwiki.bench) — mesma fonte."""
    from .bench import main as bench_main
    return bench_main(args.rest)


def cmd_models(s: Settings, args) -> int:
    """models — mostra a resolução do modelo local (ADR-42).

    Torna inspecionável o que antes era invisível: qual entrada da escada
    ganhou, por que as outras foram recusadas (ausente × não cabe) e qual
    o orçamento de memória da máquina. `--recommend` imprime só o nome a
    baixar, para o pull_models.sh consumir.
    """
    import json as _json
    from .models.router import ModelRouter, _total_ram_bytes
    router = ModelRouter(s)
    installed = router.installed_models()
    budget = router.memory_budget_bytes()
    ladder = []
    for candidate in router._chat_ladder():
        name = next((n for n in (candidate, f"{candidate}:latest")
                     if n in installed), None)
        if name is None:
            status, size = "ausente", None
        elif budget and installed[name] > budget:
            status, size = "nao_cabe", installed[name]
        else:
            status, size = "utilizavel", installed[name]
        ladder.append({"candidate": candidate, "status": status,
                       "size_gb": round(size / 1e9, 2) if size else None})
    resolved = router.resolve_chat()
    if getattr(args, "recommend", False):
        # primeiro utilizável; senão o menor candidato que caberia
        print(resolved or (ladder[-1]["candidate"] if ladder else ""))
        return 0
    print(_json.dumps({
        "resolved_chat": resolved,
        "embed": s.models["local"].get("embed"),
        "ram_total_gb": round(_total_ram_bytes() / 1e9, 2),
        "memory_budget_gb": round(budget / 1e9, 2),
        "memory_fraction": s.models["local"].get("memory_fraction", 0.6),
        "ladder": ladder,
        "installed": {k: round(v / 1e9, 2) for k, v in installed.items()},
    }, indent=1, ensure_ascii=False))
    return 0 if resolved else 1


def cmd_epistemics(s: Settings, args) -> int:
    """epistemics lint|list|show <id>|evaluations <id> — a MESMA
    implementação do painel e dos testes (harness.epistemics + facade)."""
    import json as _json
    facade = CurationFacade(s)
    if args.op == "lint":
        result = facade.epistemics_lint()
        for f in result["findings"]:
            where = f["mechanism_id"] or "<registro>"
            print(f"{f['severity']:5s} {f['code']:40s} {where}: "
                  f"{f['message']}")
        print(f"\n{result['mechanisms']} mecanismo(s), "
              f"{len(result['findings'])} finding(s)")
        return 0 if result["ok"] else 1
    if args.op == "list":
        overview = facade.epistemics_overview()
        for m in overview["mechanisms"]:
            fallback = ",".join(m["fallback"]) or "-"
            print(f"{m['mechanism_id']:32s} {m['guarantee_kind']:24s} "
                  f"{m['evaluation_status']:20s} fallback={fallback}")
        return 0
    if not args.mechanism:
        print("informe o mechanism-id", file=sys.stderr)
        return 2
    if args.op == "show":
        try:
            data = facade.epistemics_mechanism(args.mechanism)
        except KeyError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(_json.dumps(data, indent=1, ensure_ascii=False))
        return 0
    if args.op == "evaluations":
        for env in facade.epistemics_evaluations(args.mechanism):
            print(_json.dumps(env, ensure_ascii=False))
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="llmwiki")
    ap.add_argument("--config", help="caminho de config YAML alternativo")
    sub = ap.add_subparsers(dest="cmd", required=True)

    okf = sub.add_parser("okf", help="operações no bundle OKF")
    okf_sub = okf.add_subparsers(dest="okf_cmd", required=True)
    lint = okf_sub.add_parser("lint")
    lint.add_argument("--mode", choices=["write", "release"], default="write")
    lint.set_defaults(fn=cmd_lint)
    okf_sub.add_parser("index").set_defaults(fn=cmd_index)
    okf_sub.add_parser("bootstrap").set_defaults(fn=cmd_bootstrap)

    doctor = sub.add_parser("doctor", help="verifica/repara invariantes")
    doctor.add_argument("--repair", action="store_true")
    doctor.set_defaults(fn=cmd_doctor)
    sub.add_parser("checkpoints", help="cadeia de derivações e frescor de cada"
                   ).set_defaults(fn=cmd_checkpoints)
    sub.add_parser("themes", help="temas com identidade e última época"
                   ).set_defaults(fn=cmd_themes)
    backup = sub.add_parser("backup", help="backup lógico verificável")
    backup.add_argument("op", choices=["create", "verify", "list", "restore"])
    backup.add_argument("path", nargs="?", default=None)
    backup.add_argument("--dry-run", action="store_true", dest="dry_run")
    backup.add_argument("--force", action="store_true")
    backup.set_defaults(fn=cmd_backup)
    curate = sub.add_parser(
        "curate", help="atos de curadoria humana (supersede/invalidate)")
    curate.add_argument("act")
    curate.add_argument("params", nargs="*", default=[],
                        metavar="chave=valor")
    curate.add_argument("--dry-run", action="store_true", dest="dry_run")
    curate.set_defaults(fn=cmd_curate)
    bench = sub.add_parser(
        "bench", help="benchmarks reprodutíveis (ADR-39; ver benchmarks/)")
    bench.add_argument("rest", nargs="*", default=[])
    bench.set_defaults(fn=cmd_bench)
    models = sub.add_parser(
        "models", help="resolução do modelo local (escada, ADR-42)")
    models.add_argument("--recommend", action="store_true",
                        help="imprime só o modelo a usar/baixar")
    models.set_defaults(fn=cmd_models)
    epistemics = sub.add_parser(
        "epistemics", help="contratos epistemológicos (epistemics.toml)")
    epistemics.add_argument("op", choices=["lint", "list", "show",
                                           "evaluations"])
    epistemics.add_argument("mechanism", nargs="?", default=None)
    epistemics.set_defaults(fn=cmd_epistemics)
    seed = sub.add_parser("seed", help="dados pré-definidos (idempotente)")
    seed.add_argument("--file", default=None)
    seed.set_defaults(fn=cmd_seed)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("jobs").set_defaults(fn=cmd_jobs)
    sub.add_parser("daemon").set_defaults(fn=cmd_daemon)
    sub.add_parser("cold").set_defaults(fn=cmd_cold)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("page")
    freeze.add_argument("--force", action="store_true")
    freeze.set_defaults(fn=cmd_freeze)
    recycle = sub.add_parser("recycle")
    recycle.add_argument("page")
    recycle.set_defaults(fn=cmd_recycle)

    enq = sub.add_parser("enqueue")
    enq.add_argument("type")
    enq.add_argument("payload", nargs="?", default="{}")
    enq.set_defaults(fn=cmd_enqueue)

    ask = sub.add_parser("ask")
    ask.add_argument("query")
    ask.add_argument("--deep", action="store_true")
    ask.add_argument("--local", action="store_true")
    ask.set_defaults(fn=cmd_ask)

    args = ap.parse_args(argv)
    s = Settings.load(args.config)
    return args.fn(s, args)


if __name__ == "__main__":
    sys.exit(main())
