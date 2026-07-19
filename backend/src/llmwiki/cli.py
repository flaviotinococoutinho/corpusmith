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


def cmd_backup(s: Settings, args) -> int:
    """backup create|verify|list|restore [--dry-run] [--force] [path]"""
    from .usecases.backup_restore import (CreateBackup, RestoreBackup,
                                          list_backups, verify_backup)
    import json as _json
    if args.op == "create":
        print(_json.dumps(CreateBackup(s, args.path).execute(), indent=1))
    elif args.op == "verify":
        result = verify_backup(args.path)
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
    backup = sub.add_parser("backup", help="backup lógico verificável")
    backup.add_argument("op", choices=["create", "verify", "list", "restore"])
    backup.add_argument("path", nargs="?", default=None)
    backup.add_argument("--dry-run", action="store_true", dest="dry_run")
    backup.add_argument("--force", action="store_true")
    backup.set_defaults(fn=cmd_backup)
    bench = sub.add_parser(
        "bench", help="benchmarks reprodutíveis (ADR-39; ver benchmarks/)")
    bench.add_argument("rest", nargs="*", default=[])
    bench.set_defaults(fn=cmd_bench)
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
