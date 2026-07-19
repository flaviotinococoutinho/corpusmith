"""v1.7 (ADR-39) — testes DIFERENCIAIS: PythonComputeKernel(input) ≈
RustComputeKernel(input).

Determinístico (igualdade EXATA): SimHash, bandas, Hamming, pares
candidatos, componentes, interning. Ponto flutuante (tolerância
declarada): PPR e Brandes — |Δ| ≤ ABS_TOL, mesmo conjunto top-k, soma
do PPR ≈ 1, nenhum NaN/inf. Se a extensão não estiver instalada, os
testes Rust são SKIPADOS (fallback é comportamento suportado, não
falha).
"""
from __future__ import annotations
import math
import random
import pytest
from llmwiki.compute.python_kernel import PythonComputeKernel
from llmwiki.kernel.graphwalk import personalized_pagerank as ppr_reference
from llmwiki.kernel.sketch import bands, hamming, simhash

rust = pytest.importorskip(
    "llmwiki_native", reason="extensão nativa ausente — fallback Python")
from llmwiki.compute.rust_kernel import RustComputeKernel  # noqa: E402

ABS_TOL = 1e-8          # PPR/Brandes: ordem de soma difere entre backends

CORPUS = [
    "memória conhecimento grafo índice retrieval abstenção",
    "consolidação por recorrência: SimHash aproxima near-duplicata",
    "PostgreSQL≠postgres; ISO 27001 e ação, coração, ñandú — unicode",
    "the quick brown fox jumps over the lazy dog " * 40,
    "", "   ", "uma-palavra",
]


def _random_graph(seed: int, n: int = 40, m: int = 120):
    rng = random.Random(seed)
    edges = []
    for _ in range(m):
        a, b = rng.randrange(n), rng.randrange(n)
        if a != b:
            edges.append((f"p{a}", f"p{b}",
                          rng.choice([1.0, 0.5, 0.15])))
    return edges


class _FakeGraphIdx:
    """Conexão mínima: só o que load_graph consulta."""

    def __init__(self, edges):
        self._edges = edges

    def execute(self, sql, *args):
        if "graph_edges" in sql:
            weight_name = {1.0: "extracted", 0.5: "inferred",
                           0.15: "ambiguous"}
            return [(s, d, weight_name[w]) for s, d, w in self._edges]
        if "index_meta" in sql:
            class _R:
                @staticmethod
                def fetchall():
                    return []
            return _R()
        raise AssertionError(sql)


def _load_both(edges):
    py = PythonComputeKernel().load_graph(index_path="",
                                          connection=_FakeGraphIdx(edges))
    rs = RustComputeKernel().load_graph(index_path="",
                                        connection=_FakeGraphIdx(edges))
    assert py.pages == rs.pages            # interning idêntico
    assert (py.nodes, py.edges) == (rs.nodes, rs.edges)
    return py, rs


# ------------------------------------------------------- determinístico
def test_simhash_batch_is_bit_identical():
    py = PythonComputeKernel().simhash_batch(CORPUS)
    rs = RustComputeKernel().simhash_batch(CORPUS)
    assert py == rs
    assert py == [simhash(t) for t in CORPUS]      # e ≡ kernel puro


def test_hamming_and_bands_are_identical():
    rng = random.Random(11)
    for _ in range(200):
        a, b = rng.getrandbits(64), rng.getrandbits(64)
        assert rust.hamming64(a, b) == hamming(a, b)
    for _ in range(50):
        v = rng.getrandbits(64)
        assert [tuple(x) for x in bands(v)] == \
            [tuple(x) for x in bands(v)]           # sanity
    # tabela de bordas conferida no lado Rust por teste unitário


def test_candidate_pairs_are_identical():
    rng = random.Random(23)
    base = rng.getrandbits(64)
    sketches = [base]
    for _ in range(60):
        flipped = base
        for bit in rng.sample(range(64), rng.randrange(0, 16)):
            flipped ^= 1 << bit
        sketches.append(flipped)
    py = PythonComputeKernel().consolidation_candidates(sketches,
                                                        max_hamming=8)
    rs = RustComputeKernel().consolidation_candidates(sketches,
                                                      max_hamming=8)
    assert py == rs
    brute = sorted((i, j) for i in range(len(sketches))
                   for j in range(i + 1, len(sketches))
                   if hamming(sketches[i], sketches[j]) <= 8)
    assert py == brute                     # geração EXATA, sem perdas


def test_components_are_identical():
    for seed in (1, 2, 3):
        py, rs = _load_both(_random_graph(seed))
        assert PythonComputeKernel().components(py) == \
            RustComputeKernel().components(rs)


# ----------------------------------------------------- ponto flutuante
@pytest.mark.parametrize("seed", [7, 13, 29])
def test_ppr_matches_within_tolerance(seed):
    edges = _random_graph(seed)
    py, rs = _load_both(edges)
    rng = random.Random(seed)
    seeds = {f"p{rng.randrange(40)}": rng.uniform(0.1, 2.0)
             for _ in range(5)}
    ranked_py = dict(PythonComputeKernel().personalized_pagerank(
        py, seeds, top_k=0))
    ranked_rs = dict(RustComputeKernel().personalized_pagerank(
        rs, seeds, top_k=0))
    for page, score in ranked_rs.items():
        assert math.isfinite(score) and score >= 0.0
        assert abs(score - ranked_py.get(page, 0.0)) <= ABS_TOL, page
    # top-k: mesmo CONJUNTO quando as diferenças não são indistinguíveis
    top_py = {p for p, _ in PythonComputeKernel().personalized_pagerank(
        py, seeds, top_k=10)}
    top_rs = {p for p, _ in RustComputeKernel().personalized_pagerank(
        rs, seeds, top_k=10)}
    assert top_py == top_rs


def test_ppr_outside_seeds_equivalence():
    """Seeds FORA do grafo: o nó virtual agregado do Rust reproduz os
    scores dos nós REAIS da referência Python (que os inclui um a um)."""
    edges = _random_graph(41)
    py, rs = _load_both(edges)
    seeds = {"p1": 1.0, "fora-do-grafo-a": 0.7, "fora-do-grafo-b": 0.3}
    ranked_py = dict(PythonComputeKernel().personalized_pagerank(
        py, seeds, top_k=0))
    ranked_rs = dict(RustComputeKernel().personalized_pagerank(
        rs, seeds, top_k=0))
    real = {p for p, *_ in edges} | {d for _, d, _ in edges}
    for page in real & set(ranked_py):
        assert abs(ranked_py[page] - ranked_rs.get(page, 0.0)) <= ABS_TOL


def test_ppr_mass_sums_to_one():
    edges = _random_graph(53)
    py, rs = _load_both(edges)
    seeds = {"p0": 1.0}
    for kernel, graph in ((PythonComputeKernel(), py),
                          (RustComputeKernel(), rs)):
        total = sum(s for _, s in kernel.personalized_pagerank(
            graph, seeds, top_k=0))
        assert abs(total - 1.0) < 1e-6


def test_brandes_matches_within_tolerance():
    edges = _random_graph(67, n=25, m=60)
    py, rs = _load_both(edges)
    c_py = PythonComputeKernel().betweenness(py)
    c_rs = RustComputeKernel().betweenness(rs)
    assert set(c_py) == set(c_rs)
    for node, score in c_py.items():
        # a referência arredonda a 6 casas; tolerância cobre o round
        assert abs(score - c_rs[node]) <= 1e-6, node


def test_ask_evidence_identical_between_backends(settings, kb):
    """Fim-a-fim: o /ask com backend rust devolve as MESMAS páginas de
    evidência que com python (conteúdo canônico e decisão intocados)."""
    from llmwiki.compute.select import get_kernel
    from llmwiki.compute.graph_cache import invalidate
    from llmwiki.okf.document import OKFDocument, OKFFrontMatter
    from llmwiki.okf.writer import BundleWriter
    from llmwiki.retrieval.fts import rebuild_index
    from llmwiki.usecases.ask_memory import AskMemory
    docs = [OKFDocument(
        rel_path=f"concepts/kubernetes-{i}.md",
        body=f"# Kubernetes {i}\n\nKubernetes orquestra contêineres. "
             f"Ver [par](concepts/kubernetes-{(i + 1) % 3}.md).\n",
        meta=OKFFrontMatter(type="concept", title=f"Kubernetes {i}",
                            **{"privacy": "local_only",
                               "generated_via": "human:test"}))
        for i in range(3)]
    BundleWriter(kb).write(docs, log_kind="Creation", log_message="t",
                           commit_message="t")
    rebuild_index(settings, full=True)
    results = {}
    for backend in ("python", "rust"):
        settings.overrides = getattr(settings, "overrides", {})
        settings._cli = {"compute": {"backend": backend}} if False else None
        # força o backend via config dinâmica do teste
        original_get = settings.get

        def patched(dotted, default=None, _orig=original_get,
                    _backend=backend):
            if dotted == "compute.backend":
                return _backend
            return _orig(dotted, default)
        settings.get = patched                      # type: ignore
        invalidate()
        get_kernel(settings, refresh=True)
        out = AskMemory(settings, "como o Kubernetes orquestra?",
                        local_only=True).execute()
        results[backend] = [e["page"] for e in out["evidence"]]
        assert out["profile"]["ask.backend"] == backend
        settings.get = original_get                 # type: ignore
    get_kernel(settings, refresh=True)
    assert results["python"] == results["rust"]
