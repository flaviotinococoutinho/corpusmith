"""v1.7 (ADR-39 §15) — property-based tests do compute plane
(Hypothesis). As propriedades valem para AMBOS os backends; quando a
extensão nativa existe, cada propriedade roda também em Rust.
"""
from __future__ import annotations
import random
import pytest
from hypothesis import given, settings as hsettings, strategies as st
from corpusmith.compute.graph_cache import cached_graph, invalidate
from corpusmith.compute.python_kernel import PythonComputeKernel
from corpusmith.kernel.graphwalk import personalized_pagerank
from corpusmith.kernel.sketch import bands, hamming, simhash

try:
    import corpusmith_native as native
except ImportError:                       # fallback: propriedades só Python
    native = None

u64 = st.integers(min_value=0, max_value=2**64 - 1)


@given(u64)
def test_hamming_self_is_zero(x):
    assert hamming(x, x) == 0
    if native:
        assert native.hamming64(x, x) == 0


@given(u64, u64)
def test_hamming_is_symmetric(a, b):
    assert hamming(a, b) == hamming(b, a)
    if native:
        assert native.hamming64(a, b) == native.hamming64(b, a) \
            == hamming(a, b)


@given(u64, st.sets(st.integers(min_value=0, max_value=63),
                    max_size=8))
def test_pairs_with_hamming_le8_share_a_band(base, flips):
    """Casa de pombos: hamming ≤ 8 ⇒ ao menos uma das 9 bandas igual."""
    other = base
    for bit in flips:
        other ^= 1 << bit
    assert set(bands(base)) & set(bands(other)), \
        f"hamming={hamming(base, other)} sem banda comum"


@given(st.lists(u64, min_size=2, max_size=24), st.integers(0, 12))
@hsettings(max_examples=40, deadline=None)
def test_candidate_generation_loses_no_pair(sketches, max_hamming):
    """Nenhum par que satisfaz o predicado (hamming ≤ min(max, 8)) é
    perdido pela geração por bandas — completude EXATA no limiar ≤ 8."""
    threshold = min(max_hamming, 8)
    got = set(PythonComputeKernel().consolidation_candidates(
        sketches, max_hamming=threshold))
    expected = {(i, j) for i in range(len(sketches))
                for j in range(i + 1, len(sketches))
                if hamming(sketches[i], sketches[j]) <= threshold}
    assert got == expected
    if native:
        a, b = native.candidate_pairs64(list(sketches), threshold)
        assert set(zip(a, b)) == expected


import unicodedata

# LIMITE DE EQUIVALÊNCIA declarado (contrato native_sketch_kernel):
# paridade bit-a-bit vale para caracteres ATRIBUÍDOS na versão Unicode
# do CPython em uso (3.11 = Unicode 14). Pontos de código atribuídos só
# em versões mais novas (ex.: Kawi U+11F02, Unicode 15) tokenizam
# diferente entre as tabelas do runtime e as do crate — achado deste
# property test, documentado em epistemics.toml.
_assigned = st.characters(
    codec="utf-8").filter(lambda c: unicodedata.category(c) != "Cn")


@given(st.text(alphabet=_assigned, max_size=400), st.integers(1, 5))
@hsettings(max_examples=60, deadline=None)
def test_simhash_unicode_extremo_nao_quebra_e_backends_coincidem(text,
                                                                 shingle):
    """Unicode arbitrário ATRIBUÍDO (inclusive vazio/controle/combinantes)
    falha de forma controlada em NENHUM backend e coincide bit a bit."""
    py = simhash(text, shingle=shingle)
    assert 0 <= py < 2**64
    if native:
        assert native.simhash64_batch([text], shingle) == [py]


def _graph(rng: random.Random, n: int, m: int):
    adjacency: dict[str, dict[str, float]] = {}
    for _ in range(m):
        a, b = f"n{rng.randrange(n)}", f"n{rng.randrange(n)}"
        if a == b:
            continue
        adjacency.setdefault(a, {})
        adjacency.setdefault(b, {})
        w = rng.choice([1.0, 0.5, 0.15])
        adjacency[a][b] = adjacency[a].get(b, 0.0) + w
        adjacency[b][a] = adjacency[b].get(a, 0.0) + w
    return adjacency


@given(st.integers(0, 10_000))
@hsettings(max_examples=25, deadline=None)
def test_ppr_mass_nonnegative_and_sums_to_one(seed):
    rng = random.Random(seed)
    adjacency = _graph(rng, 15, 30)
    seeds = {f"n{rng.randrange(15)}": rng.uniform(0.1, 1.0)}
    rank = personalized_pagerank(adjacency, seeds)
    if not rank:
        return
    assert all(score >= 0.0 for score in rank.values())
    assert abs(sum(rank.values()) - 1.0) < 1e-6


@given(st.integers(0, 10_000), st.integers(1, 8))
@hsettings(max_examples=25, deadline=None)
def test_reducing_top_k_never_introduces_new_item(seed, k):
    rng = random.Random(seed)
    kernel = PythonComputeKernel()

    class _Idx:
        def execute(self, sql, *a):
            if "graph_edges" in sql:
                out = []
                for _ in range(30):
                    x, y = rng.randrange(15), rng.randrange(15)
                    if x != y:
                        out.append((f"n{x}", f"n{y}", "extracted"))
                return out

            class _R:
                @staticmethod
                def fetchall():
                    return []
            return _R()

    graph = kernel.load_graph(index_path="", connection=_Idx())
    if not graph.nodes:
        return
    seeds = {graph.pages[0]: 1.0}
    bigger = kernel.personalized_pagerank(graph, seeds, top_k=k + 4)
    smaller = kernel.personalized_pagerank(graph, seeds, top_k=k)
    assert {p for p, _ in smaller} <= {p for p, _ in bigger}


def test_cache_same_generation_returns_same_graph_and_change_invalidates():
    invalidate()
    kernel = PythonComputeKernel()

    class _Idx:
        def execute(self, sql, *a):
            if "graph_edges" in sql:
                return [("a", "b", "extracted")]

            class _R:
                @staticmethod
                def fetchall():
                    return []
            return _R()

    first = cached_graph(kernel, index_path="", connection=_Idx(),
                         generation="g1")
    again = cached_graph(kernel, index_path="", connection=_Idx(),
                         generation="g1")
    assert first is again                       # mesmo snapshot (hit)
    rebuilt = cached_graph(kernel, index_path="", connection=_Idx(),
                           generation="g2")
    assert rebuilt is not first                 # geração nova invalida
    invalidate()


def test_empty_corpus_produces_valid_output():
    kernel = PythonComputeKernel()
    assert kernel.simhash_batch([]) == []
    assert kernel.consolidation_candidates([]) == []
    if native:
        assert native.simhash64_batch([], 3) == []
        assert native.candidate_pairs64([], 8) == ([], [])


def test_giant_document_respects_limit():
    """Documento gigante: o chamador trunca (consolidate corta em 100k);
    aqui, o sketch de 1 MB termina e coincide entre backends."""
    text = "palavra repetida em documento gigante " * 30_000
    py = simhash(text[:100_000])
    if native:
        assert native.simhash64_batch([text[:100_000]], 3) == [py]


def test_selection_and_fallback_are_observable(settings, monkeypatch):
    """auto→rust quando disponível; indisponível ⇒ python com MOTIVO;
    rust exigido sem fallback ⇒ erro explícito (nunca silencioso)."""
    from corpusmith.compute import select
    kernel = select.get_kernel(settings, refresh=True)
    report = select.selection_report()
    if native:
        assert kernel.backend_info().name == "rust"
        assert report["effective"] == "rust"
    # simula extensão quebrada
    def broken():
        raise ImportError("simulada")
    monkeypatch.setattr(select, "_try_rust", broken)
    kernel = select.get_kernel(settings, refresh=True)
    report = select.selection_report()
    assert kernel.backend_info().name == "python"
    assert "simulada" in report["fallback_reason"]     # nunca oculto
    # rust exigido + fallback proibido ⇒ erro
    original_get = settings.get

    def patched(dotted, default=None):
        if dotted == "compute.backend":
            return "rust"
        if dotted == "compute.allow_fallback":
            return False
        return original_get(dotted, default)
    monkeypatch.setattr(settings, "get", patched)
    with pytest.raises(RuntimeError, match="indisponível"):
        select.get_kernel(settings, refresh=True)
    monkeypatch.undo()
    select.get_kernel(settings, refresh=True)          # restaura o real
