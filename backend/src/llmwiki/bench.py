"""Bench reprodutível (QA-2, v1.6.4): os claims dos ADRs viram medição
verificável em qualquer máquina — frio×quente do gazetteer (cache por
(kb, HEAD), claim ~92× no hit) e full×incremental do índice (claim ~29×
em 150 páginas) — sobre um bundle SINTÉTICO determinístico (semente
fixa), com saída JSON de schema versionado.

Números absolutos variam por máquina; as RAZÕES (speedups) são o que os
ADRs alegam. Nada aqui toca ~/llmwiki: o bundle sintético vive no
diretório que o chamador passar (o wrapper de script usa um temporário).
Toda escrita passa pelo BundleWriter (INV-DATA-001) — inclusive a
alteração de 1 página que mede o caminho incremental."""
from __future__ import annotations
import json
import platform
import random
import sys
import time
from pathlib import Path
from . import __version__
from .harness.runner import HarnessRunner
from .okf.authorities import load_gazetteer
from .okf.bootstrap import ensure_bundle
from .okf.bundle import BundleReader
from .okf.document import OKFDocument, OKFFrontMatter
from .okf.git_store import GitStore
from .okf.writer import BundleWriter
from .retrieval.fts import rebuild_index, search
from .settings import Settings

_VOCAB = ("memoria conhecimento grafo indice retrieval abstencao entidade "
          "curadoria consolidacao reconciliacao topologia comunidade ponte "
          "lacuna evidencia citacao orcamento ledger governanca privacidade "
          "temporal validade snapshot linhagem calibracao estrategia").split()


def synthetic_bundle(home: Path, n_pages: int, seed: int = 7) -> Settings:
    """Bundle determinístico: mesmas semente e contagem ⇒ mesmos corpos."""
    s = Settings(home=home)
    kb = s.path("knowledge")
    ensure_bundle(kb)
    rng = random.Random(seed)
    docs = []
    for i in range(n_pages):
        words = " ".join(rng.choice(_VOCAB) for _ in range(120))
        docs.append(OKFDocument(
            rel_path=f"concepts/sintetica-{i:04d}.md",
            body=f"# Sintética {i}\n\n{words}\n",
            meta=OKFFrontMatter(type="concept", title=f"Sintética {i}",
                                **{"privacy": "local_only",
                                   "generated_via": "human:bench"})))
    BundleWriter(kb).write(docs, log_kind="Creation",
                           log_message=f"bench sintético ({n_pages} páginas)",
                           commit_message="bench: bundle sintético")
    return s


def _timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return time.perf_counter() - t0, out


def run_bench(s: Settings, n_pages: int) -> dict:
    kb = s.path("knowledge")
    bundle = kb / "bundle"
    reader = BundleReader(bundle)
    # frio: o último commit mudou o HEAD, então a 1ª carga é cache miss
    t_gaz_cold, _ = _timed(lambda: load_gazetteer(reader))
    t_gaz_warm, _ = _timed(lambda: load_gazetteer(reader))
    t_full, r_full = _timed(lambda: rebuild_index(s, full=True))
    # 1 página alterada PELO caminho canônico (commita ⇒ HEAD anda)
    changed = OKFDocument(
        rel_path="concepts/sintetica-0000.md",
        body="# Sintética 0\n\nconteúdo alterado pelo bench incremental\n",
        meta=OKFFrontMatter(type="concept", title="Sintética 0",
                            **{"privacy": "local_only",
                               "generated_via": "human:bench"}))
    BundleWriter(kb).write([changed], log_kind="Update",
                           log_message="bench: 1 página alterada",
                           commit_message="bench: alteração incremental")
    t_incr, r_incr = _timed(lambda: rebuild_index(s))
    t_noop, r_noop = _timed(lambda: rebuild_index(s))
    runner = HarnessRunner(reader, GitStore(kb))
    t_lint, _ = _timed(lambda: len(runner.lint_bundle(bundle)))
    t_search, _ = _timed(lambda: len(search(s, "memoria conhecimento")))

    def ratio(slow: float, fast: float) -> float | None:
        return round(slow / fast, 1) if fast > 0 else None

    return {
        "schema": 1,
        "product_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "n_pages": n_pages,
        "counts": {"full_reindexed": r_full["reindexed"],
                   "incremental_reindexed": r_incr["reindexed"],
                   "noop_reindexed": r_noop["reindexed"]},
        "timings_s": {k: round(v, 6) for k, v in {
            "gazetteer_frio": t_gaz_cold, "gazetteer_quente": t_gaz_warm,
            "indice_full": t_full, "indice_incremental_1pg": t_incr,
            "indice_noop": t_noop, "lint_bundle": t_lint,
            "fts_search": t_search}.items()},
        "speedups": {"gazetteer_quente": ratio(t_gaz_cold, t_gaz_warm),
                     "indice_incremental_1pg": ratio(t_full, t_incr),
                     "indice_noop": ratio(t_full, t_noop)},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", type=int, default=150, metavar="N",
                        help="bundle sintético de N páginas (default 150)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--current", action="store_true",
                        help="mede o bundle ATUAL (lint/index/search; "
                             "sem sintético, sem alterar nada)")
    parser.add_argument("--json", metavar="ARQ",
                        help="grava o resultado JSON neste arquivo")
    args = parser.parse_args(argv)

    if args.current:
        s = Settings.load()
        kb = s.path("knowledge")
        reader = BundleReader(kb / "bundle")
        runner = HarnessRunner(reader, GitStore(kb))
        for label, fn in (
                ("lint_bundle", lambda: len(runner.lint_bundle(kb / "bundle"))),
                ("rebuild_index", lambda: rebuild_index(s)),
                ("fts.search", lambda: len(search(s, "arquitetura decisão")))):
            dt, out = _timed(fn)
            print(f"{label:20s} {dt:8.3f}s  {out}")
        return 0

    with tempfile.TemporaryDirectory(prefix="llmwiki-bench-") as tmp:
        s = synthetic_bundle(Path(tmp) / "home", args.synthetic, args.seed)
        result = run_bench(s, args.synthetic)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
