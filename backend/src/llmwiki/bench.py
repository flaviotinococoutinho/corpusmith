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


# ================= v1.7 (ADR-39): verbos de benchmark do compute plane
# Fixtures determinísticas por semente; resultados em JSON schema 1;
# medição Python × Rust com speedup REAL (nada estimado). Declaração de
# cada métrica: benchmarks/METRICS.md.

FIXTURES = {"tiny": 30, "small": 150, "medium": 500}


def _percentiles(samples: list[float]) -> dict:
    ordered = sorted(samples)
    n = len(ordered)

    def pct(p: float) -> float:
        return round(ordered[min(n - 1, int(p * n))], 6)
    out = {"n": n, "p50": pct(0.50), "p95": pct(0.95),
           "mean": round(sum(ordered) / n, 6)}
    if n >= 100:
        out["p99"] = pct(0.99)
    return out


def _synthetic_graph(n_nodes: int, degree: int, seed: int):
    rng = random.Random(seed)
    edges = []
    for v in range(n_nodes):
        for _ in range(degree):
            u = rng.randrange(n_nodes)
            if u != v:
                edges.append((f"p{v}", f"p{u}",
                              rng.choice(["extracted", "inferred",
                                          "ambiguous"])))
    return edges


class _EdgeConn:
    """Conexão fake mínima para load_graph em memória."""

    def __init__(self, edges):
        self._edges = edges

    def execute(self, sql, *a):
        if "graph_edges" in sql:
            return list(self._edges)

        class _R:
            @staticmethod
            def fetchall():
                return []
        return _R()


def _kernels(backends: list[str]):
    from .compute.python_kernel import PythonComputeKernel
    out = {}
    if "python" in backends:
        out["python"] = PythonComputeKernel()
    if "rust" in backends:
        try:
            from .compute.rust_kernel import RustComputeKernel
            out["rust"] = RustComputeKernel()
        except Exception as e:
            out["rust_unavailable"] = f"{type(e).__name__}: {e}"
    return out


def bench_graph(*, nodes: int = 5_000, degree: int = 4, seed: int = 7,
                rounds: int = 5,
                backends: list[str] = ("python", "rust")) -> dict:
    """PPR + Brandes por backend sobre o MESMO grafo sintético.
    Speedup = wall Python / wall Rust (medido, por rodada)."""
    edges = _synthetic_graph(nodes, degree, seed)
    kernels = _kernels(list(backends))
    rng = random.Random(seed)
    seeds = {f"p{rng.randrange(nodes)}": rng.uniform(0.5, 2.0)
             for _ in range(6)}
    report: dict = {"schema": 1, "kind": "graph",
                    "product_version": __version__,
                    "nodes": nodes, "edges": len(edges), "rounds": rounds,
                    "backends": {}}
    for name, kernel in kernels.items():
        if name == "rust_unavailable":
            report["backends"]["rust"] = {"unavailable": kernel}
            continue
        t_load, graph = _timed(lambda k=kernel: k.load_graph(
            index_path="", connection=_EdgeConn(edges)))
        ppr_ms, brandes_ms = [], []
        for _ in range(rounds):
            dt, _ = _timed(lambda k=kernel, g=graph:
                           k.personalized_pagerank(g, seeds, top_k=12))
            ppr_ms.append(dt * 1000)
        for _ in range(max(1, rounds // 2)):
            dt, _ = _timed(lambda k=kernel, g=graph:
                           k.betweenness(g, top_k=10))
            brandes_ms.append(dt * 1000)
        report["backends"][name] = {
            "load_ms": round(t_load * 1000, 3),
            "ppr_ms": _percentiles(ppr_ms),
            "brandes_ms": _percentiles(brandes_ms)}
    both = report["backends"]
    if "python" in both and "rust" in both and "ppr_ms" in both.get(
            "rust", {}):
        report["speedup"] = {
            "ppr": round(both["python"]["ppr_ms"]["p50"]
                         / both["rust"]["ppr_ms"]["p50"], 1),
            "brandes": round(both["python"]["brandes_ms"]["p50"]
                             / both["rust"]["brandes_ms"]["p50"], 1)}
    return report


def bench_consolidate(*, documents: int = 400, seed: int = 7,
                      rounds: int = 3,
                      backends: list[str] = ("python", "rust")) -> dict:
    """SimHash em lote + geração de pares candidatos por backend, com
    ~10% de near-duplicatas plantadas (mesma semente ⇒ mesmo corpus)."""
    rng = random.Random(seed)
    texts = []
    for i in range(documents):
        words = " ".join(rng.choice(_VOCAB) for _ in range(300))
        texts.append(words)
        if i % 10 == 0:                       # near-duplicata plantada
            texts.append(words.replace("memoria", "memorias", 1))
    kernels = _kernels(list(backends))
    report: dict = {"schema": 1, "kind": "consolidate",
                    "product_version": __version__,
                    "documents": len(texts), "rounds": rounds,
                    "backends": {}}
    reference_pairs = None
    for name, kernel in kernels.items():
        if name == "rust_unavailable":
            report["backends"]["rust"] = {"unavailable": kernel}
            continue
        sketch_ms, cand_ms = [], []
        sketches = []
        for _ in range(rounds):
            dt, sketches = _timed(lambda k=kernel: k.simhash_batch(texts))
            sketch_ms.append(dt * 1000)
        pairs = []
        for _ in range(rounds):
            dt, pairs = _timed(lambda k=kernel, s=sketches:
                               k.consolidation_candidates(s, max_hamming=8))
            cand_ms.append(dt * 1000)
        if reference_pairs is None:
            reference_pairs = pairs
        else:
            assert pairs == reference_pairs, \
                "backends divergiram nos pares candidatos"
        report["backends"][name] = {
            "sketch_ms": _percentiles(sketch_ms),
            "candidates_ms": _percentiles(cand_ms),
            "candidate_pairs": len(pairs)}
    both = report["backends"]
    if "python" in both and "sketch_ms" in both.get("rust", {}):
        report["speedup"] = {
            "sketch": round(both["python"]["sketch_ms"]["p50"]
                            / both["rust"]["sketch_ms"]["p50"], 1),
            "candidates": round(both["python"]["candidates_ms"]["p50"]
                                / max(both["rust"]["candidates_ms"]["p50"],
                                      1e-9), 1)}
    return report


def bench_ask(*, n_pages: int = 150, asks: int = 12, seed: int = 7) -> dict:
    """/ask fim-a-fim (extrativo local — sem modelo) sobre bundle
    sintético indexado: percentis do total e média por estágio, com o
    backend efetivo registrado no perfil."""
    import tempfile
    from .usecases.ask_memory import AskMemory
    from .compute.graph_cache import graph_cache_stats, invalidate
    with tempfile.TemporaryDirectory(prefix="llmwiki-bench-ask-") as tmp:
        s = synthetic_bundle(Path(tmp) / "home", n_pages, seed)
        rebuild_index(s, full=True)
        invalidate()
        rng = random.Random(seed)
        totals, profiles = [], []
        for i in range(asks):
            query = ("como " + " ".join(rng.choice(_VOCAB)
                                        for _ in range(3)) + "?")
            out = AskMemory(s, query, local_only=True).execute()
            profile = out.get("profile", {})
            totals.append(profile.get("ask.total_ms", 0.0))
            profiles.append(profile)
        stage_means = {}
        for key in sorted({k for p in profiles for k in p
                           if k.endswith("_ms")}):
            values = [p.get(key, 0.0) for p in profiles]
            stage_means[key] = round(sum(values) / len(values), 3)
        return {"schema": 1, "kind": "ask",
                "product_version": __version__,
                "n_pages": n_pages, "asks": asks,
                "backend": profiles[0].get("ask.backend") if profiles
                else None,
                "total_ms": _percentiles(totals),
                "stage_mean_ms": stage_means,
                "graph_cache": graph_cache_stats()}


def _bench_root() -> Path:
    return Path(__file__).resolve().parents[3] / "benchmarks"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="verb")

    core = sub.add_parser("core", help="frio×quente + full×incremental "
                                       "(QA-2, comportamento original)")
    core.add_argument("--synthetic", type=int, default=150)
    core.add_argument("--seed", type=int, default=7)
    core.add_argument("--json", default=None)

    ask_p = sub.add_parser("ask", help="/ask fim-a-fim por estágio")
    ask_p.add_argument("--pages", type=int, default=150)
    ask_p.add_argument("--asks", type=int, default=12)
    ask_p.add_argument("--json", default=None)

    graph_p = sub.add_parser("graph", help="PPR/Brandes python×rust")
    graph_p.add_argument("--nodes", type=int, default=5000)
    graph_p.add_argument("--degree", type=int, default=4)
    graph_p.add_argument("--rounds", type=int, default=5)
    graph_p.add_argument("--backend", choices=["python", "rust", "both"],
                         default="both")
    graph_p.add_argument("--json", default=None)

    cons_p = sub.add_parser("consolidate",
                            help="SimHash/candidatos python×rust")
    cons_p.add_argument("--documents", type=int, default=400)
    cons_p.add_argument("--rounds", type=int, default=3)
    cons_p.add_argument("--backend", choices=["python", "rust", "both"],
                        default="both")
    cons_p.add_argument("--json", default=None)

    cmp_p = sub.add_parser("compare", help="graph+consolidate nos dois "
                                           "backends + speedups")
    cmp_p.add_argument("--json", default=None)

    fix_p = sub.add_parser("generate-fixture",
                           help="materializa fixture determinística")
    fix_p.add_argument("name", choices=sorted(FIXTURES))
    fix_p.add_argument("--seed", type=int, default=7)

    index_p = sub.add_parser("index", help="alias de core")
    index_p.add_argument("--synthetic", type=int, default=150)
    index_p.add_argument("--seed", type=int, default=7)
    index_p.add_argument("--json", default=None)

    # compat: sem verbo ⇒ comportamento original (QA-2)
    parser.add_argument("--synthetic", type=int, default=150)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--current", action="store_true")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    def emit(result: dict) -> int:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        if getattr(args, "json", None):
            Path(args.json).write_text(
                json.dumps(result, ensure_ascii=False, indent=1) + "\n")
        return 0

    backends = {"both": ["python", "rust"]}.get(
        getattr(args, "backend", "both"),
        [getattr(args, "backend", "both")])

    if args.verb == "ask":
        return emit(bench_ask(n_pages=args.pages, asks=args.asks))
    if args.verb == "graph":
        return emit(bench_graph(nodes=args.nodes, degree=args.degree,
                                rounds=args.rounds, backends=backends))
    if args.verb == "consolidate":
        return emit(bench_consolidate(documents=args.documents,
                                      rounds=args.rounds,
                                      backends=backends))
    if args.verb == "compare":
        return emit({"schema": 1, "kind": "compare",
                     "product_version": __version__,
                     "graph": bench_graph(),
                     "consolidate": bench_consolidate()})
    if args.verb == "generate-fixture":
        home = _bench_root() / "fixtures" / args.name / "home"
        if home.exists():
            print(f"fixture já existe: {home}")
            return 0
        synthetic_bundle(home, FIXTURES[args.name], args.seed)
        print(f"fixture {args.name}: {FIXTURES[args.name]} páginas em "
              f"{home}")
        return 0
    if args.verb in ("core", "index"):
        with tempfile.TemporaryDirectory(prefix="llmwiki-bench-") as tmp:
            s = synthetic_bundle(Path(tmp) / "home", args.synthetic,
                                 args.seed)
            return emit(run_bench(s, args.synthetic))

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
    return emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
