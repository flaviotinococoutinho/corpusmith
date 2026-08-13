"""QA-2 (P2 do backlog v1.3): harness de bench REPRODUTÍVEL — os claims
~92× (gazetteer frio×quente por HEAD) e ~29× (índice full×incremental)
dos ADRs deixam de ser medição de sessão e viram script versionado com
bundle sintético determinístico e saída JSON de schema estável.

As asserções são SEMÂNTICAS (contagens determinísticas do reindex), não
de tempo absoluto — tempo vira flakiness em CI."""
from __future__ import annotations
from corpusmith.bench import run_bench, synthetic_bundle


def test_bench_sintetico_e_deterministico_e_completo(tmp_path):
    s = synthetic_bundle(tmp_path / "bench-home", n_pages=8)
    result = run_bench(s, n_pages=8)
    # schema estável (versionado)
    assert result["schema"] == 1
    assert result["n_pages"] == 8
    for key in ("product_version", "python", "platform",
                "timings_s", "speedups", "counts"):
        assert key in result
    # semântica do full×incremental (determinística, sem cronômetro):
    counts = result["counts"]
    assert counts["full_reindexed"] == 8       # full reindexa TUDO
    assert counts["incremental_reindexed"] == 1  # 1 página mudou ⇒ 1 reindex
    assert counts["noop_reindexed"] == 0       # nada mudou ⇒ nada refeito
    # cronômetros existem e são positivos
    assert all(v >= 0 for v in result["timings_s"].values())
    assert set(result["speedups"]) == {"gazetteer_quente",
                                       "indice_incremental_1pg",
                                       "indice_noop"}


def test_bundle_sintetico_mesma_semente_mesmo_conteudo(tmp_path):
    s1 = synthetic_bundle(tmp_path / "a", n_pages=3, seed=7)
    s2 = synthetic_bundle(tmp_path / "b", n_pages=3, seed=7)
    p1 = (s1.path("knowledge") / "bundle" / "concepts"
          / "sintetica-0001.md").read_text()
    p2 = (s2.path("knowledge") / "bundle" / "concepts"
          / "sintetica-0001.md").read_text()
    # corpo determinístico (timestamp difere; corpo após o frontmatter não)
    assert p1.split("---")[-1] == p2.split("---")[-1]
