"""QA-4 (P2 do backlog v1.3): testes de SENSIBILIDADE dos limiares
críticos de decisão — cada fronteira é exercitada dos DOIS lados, para
que mudar uma constante (ou inverter um comparador) quebre a suíte em
vez de mudar o produto em silêncio.

Cobertos aqui: clamp do Hedge [0.5, 2.0] · fatores de overlay
(preferred 1.15 / low_yield 0.8) na fusão RRF · ask.abstain_threshold ·
fronteira do orçamento do Governor · near-duplicata hamming ≤ 8 ·
fronteira de dígitos da citação [n] (QA-3). Já cobertos alhures: bandas
LSH/casa de pombos (test_v16), jitter estável e backoff (reliability)."""
from __future__ import annotations
import math
import pytest
from corpusmith.kernel.information import hedge
from corpusmith.okf.document import OKFDocument, OKFFrontMatter
from corpusmith.okf.writer import BundleWriter
from corpusmith.retrieval.fts import rebuild_index
from corpusmith.retrieval.streams import EvidenceStreams, RRF_K
from corpusmith.runtime.db import connect
from corpusmith.runtime.governor import Governor
from corpusmith.settings import Settings
from corpusmith.usecases.ask_memory import AskMemory, _invalid_citations
from corpusmith.usecases.consolidate_inbox import _Signature


# ------------------------------------------------------- Hedge clamp [.5, 2]
def test_hedge_perda_extrema_para_no_floor():
    w = hedge({"fts": 1.0}, {"fts": 100.0})
    assert w["fts"] == 0.5                       # nunca silenciado de vez


def test_hedge_ganho_extremo_para_no_ceiling():
    w = hedge({"fts": 1.0}, {"fts": -100.0})
    assert w["fts"] == 2.0                       # nunca domina de vez


def test_hedge_dentro_do_clamp_e_multiplicativo_exato():
    w = hedge({"fts": 1.0}, {"fts": 1.0}, eta=0.25)
    assert w["fts"] == pytest.approx(math.exp(-0.25))


def test_hedge_sem_perda_nao_muda_peso():
    assert hedge({"fts": 1.3}, {})["fts"] == pytest.approx(1.3)


# ------------------------------------------ overlay na fusão (1.15 / 0.8)
@pytest.mark.parametrize("status,factor", [
    ("preferred", 1.15), ("low_yield", 0.8), (None, 1.0)])
def test_overlay_multiplica_o_score_rrf_exatamente(status, factor):
    streams = EvidenceStreams()
    streams.add("fts", [{"id": 1, "page": "concepts/a.md"}])
    fused = streams.fuse(overlay={"concepts/a.md": status} if status else {})
    assert fused.top_score == pytest.approx(factor / (RRF_K + 1))


def test_overlay_contested_afunda_abaixo_de_neutro_no_mesmo_rank():
    streams = EvidenceStreams()
    streams.add("fts", [{"id": 1, "page": "concepts/a.md"},
                        {"id": 2, "page": "concepts/b.md"}])
    fused = streams.fuse(overlay={"concepts/a.md": "low_yield"})
    # a (rank 0, ×0.8 ⇒ 0.0131) perde de b (rank 1, ×1.0 ⇒ 0.0161)? NÃO:
    # 0.8/61 = 0.0131 < 1/62 = 0.0161 ⇒ b assume o topo
    assert fused.hits[0]["page"] == "concepts/b.md"


# --------------------------------------------------- ask.abstain_threshold
def _index_page(settings, kb):
    doc = OKFDocument(
        rel_path="concepts/prometheus.md",
        body="# Prometheus\n\nPrometheus coleta métricas por scraping "
             "de endpoints e armazena séries temporais.",
        meta=OKFFrontMatter(type="concept", title="Prometheus",
                            privacy="local_only"))
    BundleWriter(kb).write([doc], log_kind="Creation", log_message="m",
                           commit_message="c")
    rebuild_index(settings)


def test_threshold_acima_do_score_abstem(settings, kb):
    _index_page(settings, kb)
    high = settings.with_overrides(ask={"abstain_threshold": 1.0})
    out = AskMemory(high, "prometheus scraping").execute()
    assert out["abstained"] is True              # score RRF (~1/61) < 1.0


def test_threshold_zero_responde(settings, kb):
    _index_page(settings, kb)
    out = AskMemory(settings, "prometheus scraping").execute()
    assert out["abstained"] is False and out["evidence"]


# --------------------------------------------- fronteira do orçamento (gov)
def _gov(settings, tmp_factor):
    s = Settings(home=settings.home, budget={"daily_usd": 1.0})
    return Governor(s, connect(s.app_support / "runtime.db"))


def test_gasto_abaixo_do_orcamento_permite_api(settings):
    gov = _gov(settings, 1)
    gov.record(provider="anthropic", model="m", usd=0.99)
    assert gov.allow_api() is True               # sobra 0.01 > 0


def test_gasto_igual_ao_orcamento_bloqueia_api(settings):
    gov = _gov(settings, 2)
    gov.record(provider="anthropic", model="m", usd=1.0)
    assert gov.allow_api() is False              # sobra 0.0, e 0 > 0 é falso


def test_estimativa_que_estoura_bloqueia_na_frente(settings):
    gov = _gov(settings, 3)
    gov.record(provider="anthropic", model="m", usd=0.5)
    assert gov.allow_api(est_usd=0.5) is False   # 0.5 − 0.5 = 0 ⇒ bloqueia
    assert gov.allow_api(est_usd=0.49) is True


# --------------------------------------- near-duplicata (hamming ≤ 8) exata
def _sig(settings, kb, text):
    from corpusmith.normalize.gazetteer import Gazetteer
    return _Signature("raw/x.md", text, Gazetteer([]))


def _with_bits(base: int, bits: int) -> int:
    out = base
    for i in range(bits):
        out ^= (1 << i)
    return out


def test_hamming_8_converge_e_9_nao(settings, kb):
    a = _sig(settings, kb, "texto qualquer de fonte pendente")
    b = _sig(settings, kb, "outro texto qualquer de fonte")
    a.sketch, b.sketch = 0, _with_bits(0, 8)     # distância exata 8
    assert a.converges_with(b, min_shared=99) is True
    b.sketch = _with_bits(0, 9)                  # distância exata 9
    assert a.converges_with(b, min_shared=99) is False


# ------------------------------------- citação [n]: fronteira de dígitos
@pytest.mark.parametrize("text,invalid", [
    ("ver [99]", [99]),          # 2 dígitos: é citação e está fora
    ("ver [100]", []),           # 3 dígitos: não é citação (ano/id)
    ("ver [10]", []),            # 2 dígitos dentro da evidência
])
def test_citacao_fronteira_de_digitos(text, invalid):
    assert _invalid_citations(text, 10) == invalid
