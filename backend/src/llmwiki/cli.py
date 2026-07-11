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
