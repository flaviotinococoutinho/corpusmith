"""Metacognição assistida (v0.18) — o sistema observa COMO a memória é
usada e devolve HIPÓTESES, nunca rótulos.

Base formal: Flavell ("Metacognition and cognitive monitoring", American
Psychologist, 1979) separa conhecimento metacognitivo de regulação;
Nelson & Narens (1990) formalizam o par monitoramento→controle. Aqui:

- MONITORAMENTO: `ObserveMetacognition` minera padrões DETERMINÍSTICOS
  (SQL + aritmética, sem LLM) de ask_context × ask_outcomes ×
  cognitive_state — desempenho por estratégia, correlação de erro com
  carga declarada (fraseada como correlação, jamais causalidade), e
  calibração (Brier/overconfidence do kernel).
- CONTROLE: `ReviewObservation` é o gate humano (aceitar/rejeitar/
  suspender). Aceitar uma observação com `suggestion` aplica o ajuste
  PELA LINHAGEM de configuração (TuneConfig, source="metacog") — o
  observado só vira declarado com consentimento, com guard e rollback
  de graça (FR-14.3 da espec realizada com o maquinário da v0.16).

Observação isolada não vira padrão: `cognitive.min_support` ocorrências
no mínimo, e o texto sempre carrega n e taxa (falsa precisão é risco
nomeado — os números vão juntos da frase).
"""
from __future__ import annotations
import json
from .base import UseCase
from .cognitive_state import STRATEGIES
from .configure_system import TuneConfig
from ..kernel.calibration import brier_score, calibration_bins, overconfidence
from ..runtime.db import connect
from ..settings import Settings

REVIEW_ACTIONS = ("accepted", "rejected", "suspended")


def _pairs(rt) -> list[tuple[float, int]]:
    """(confiança, desfecho∈{0,1}) por consulta julgada."""
    return [(r["confidence"], 1 if r["verdict"] == "useful" else 0)
            for r in rt.execute(
                "SELECT c.confidence, o.verdict FROM ask_context c "
                "JOIN ask_outcomes o ON o.ask_id = c.ask_id "
                "WHERE c.confidence IS NOT NULL")]


def calibration_report(settings: Settings) -> dict:
    rt = connect(settings.app_support / "runtime.db")
    pairs = _pairs(rt)
    rt.close()
    return {"n": len(pairs), "brier": brier_score(pairs),
            "overconfidence": overconfidence(pairs),
            "bins": calibration_bins(pairs)}


def observations(settings: Settings, status: str | None = None) -> list[dict]:
    rt = connect(settings.app_support / "runtime.db")
    where, params = ("WHERE status = ?", [status]) if status else ("", [])
    rows = rt.execute(
        f"SELECT id, ts, kind, statement, support, confidence, evidence, "
        f"suggestion, status FROM metacog_observations {where} "
        f"ORDER BY id DESC LIMIT 100", params).fetchall()
    rt.close()
    return [{**dict(r),
             "evidence": json.loads(r["evidence"] or "{}"),
             "suggestion": json.loads(r["suggestion"]) if r["suggestion"]
             else None} for r in rows]


class ObserveMetacognition(UseCase):
    """Uma varredura = zero ou mais propostas novas. Dedupe por (kind,
    statement) ainda aberto — a mesma hipótese não é proposta duas vezes
    enquanto a pessoa não a julgar."""

    def __init__(self, settings: Settings, notify=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)
        self._min_support = int(settings.get("cognitive.min_support", 5))

    def execute(self) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        proposals = (self._strategy_patterns(rt)
                     + self._load_patterns(rt)
                     + self._calibration_pattern(rt))
        created = 0
        for prop in proposals:
            exists = rt.execute(
                "SELECT 1 FROM metacog_observations WHERE kind=? AND "
                "statement=? AND status IN ('proposed','accepted')",
                (prop["kind"], prop["statement"])).fetchone()
            if exists:
                continue
            rt.execute(
                "INSERT INTO metacog_observations"
                "(kind, statement, support, confidence, evidence, suggestion) "
                "VALUES (?,?,?,?,?,?)",
                (prop["kind"], prop["statement"], prop["support"],
                 prop["confidence"], json.dumps(prop["evidence"]),
                 json.dumps(prop["suggestion"]) if prop.get("suggestion")
                 else None))
            created += 1
        rt.commit()
        rt.close()
        if created:
            self._notify("metacog.observed", {"created": created})
        return {"scanned": len(proposals), "created": created}

    # ------------------------------------------------------- mineradores
    def _strategy_patterns(self, rt) -> list[dict]:
        rows = rt.execute(
            "SELECT c.strategy, COUNT(*) n, "
            "SUM(o.verdict = 'useful') useful FROM ask_context c "
            "JOIN ask_outcomes o ON o.ask_id = c.ask_id "
            "GROUP BY c.strategy").fetchall()
        total_n = sum(r["n"] for r in rows)
        total_useful = sum(r["useful"] for r in rows)
        if not total_n:
            return []
        global_rate = total_useful / total_n
        out = []
        for r in rows:
            if r["n"] < self._min_support or r["strategy"] not in STRATEGIES:
                continue
            rate = r["useful"] / r["n"]
            if rate - global_rate >= 0.15:
                out.append({
                    "kind": "strategy",
                    "statement": (
                        f"Respostas com estratégia '{r['strategy']}' foram "
                        f"úteis em {rate:.0%} das vezes (média geral "
                        f"{global_rate:.0%}, n={r['n']})."),
                    "support": r["n"], "confidence": rate,
                    "evidence": {"strategy": r["strategy"], "rate": rate,
                                 "global_rate": global_rate, "n": r["n"]},
                    "suggestion": {"profile":
                                   {"preferred_strategy": r["strategy"]}}})
        return out

    def _load_patterns(self, rt) -> list[dict]:
        high = int(self._settings.get("cognitive.high_load", 4))
        rows = rt.execute(
            "SELECT (c.load >= ?) is_high, COUNT(*) n, "
            "SUM(o.verdict != 'useful') bad FROM ask_context c "
            "JOIN ask_outcomes o ON o.ask_id = c.ask_id "
            "WHERE c.load IS NOT NULL GROUP BY is_high",
            (high,)).fetchall()
        groups = {bool(r["is_high"]): r for r in rows}
        if True not in groups or False not in groups:
            return []
        hi, lo = groups[True], groups[False]
        if min(hi["n"], lo["n"]) < self._min_support:
            return []
        hi_rate, lo_rate = hi["bad"] / hi["n"], lo["bad"] / lo["n"]
        if hi_rate - lo_rate < 0.15:
            return []
        # correlação, NUNCA causalidade (FR-15.3)
        return [{
            "kind": "load",
            "statement": (
                f"Os registros indicam mais desfechos ruins em consultas "
                f"feitas sob carga declarada alta ({hi_rate:.0%}, "
                f"n={hi['n']}) do que sob carga baixa ({lo_rate:.0%}, "
                f"n={lo['n']}). Correlação observada — não causa."),
            "support": hi["n"] + lo["n"], "confidence": hi_rate - lo_rate,
            "evidence": {"high_bad_rate": hi_rate, "low_bad_rate": lo_rate,
                         "high_n": hi["n"], "low_n": lo["n"]},
            "suggestion": None}]

    def _calibration_pattern(self, rt) -> list[dict]:
        pairs = _pairs(rt)
        if len(pairs) < self._min_support:
            return []
        gap = overconfidence(pairs)
        if gap is None or gap < 0.2:
            return []
        return [{
            "kind": "calibration",
            "statement": (
                f"A confiança média das respostas ({sum(p for p, _ in pairs) / len(pairs):.0%}) "
                f"está acima da taxa de acerto ({sum(o for _, o in pairs) / len(pairs):.0%}) "
                f"em {gap:.0%} (n={len(pairs)}) — padrão de excesso de "
                f"confiança. Vale conferir evidências antes de confiar."),
            "support": len(pairs), "confidence": gap,
            "evidence": {"brier": brier_score(pairs),
                         "overconfidence": gap, "n": len(pairs)},
            "suggestion": None}]


class ReviewObservation(UseCase):
    """O gate humano: aceitar/rejeitar/suspender. Aceite com suggestion
    aplica o tune pela linhagem (guard + ring + rollback inclusos)."""

    def __init__(self, settings: Settings, observation_id: int,
                 action: str, notify=None):
        if action not in REVIEW_ACTIONS:
            raise ValueError(f"action ∈ {REVIEW_ACTIONS}")
        self._settings = settings
        self._id = int(observation_id)
        self._action = action
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        row = rt.execute("SELECT suggestion, status FROM metacog_observations "
                         "WHERE id = ?", (self._id,)).fetchone()
        if not row:
            rt.close()
            raise KeyError(f"observação {self._id}")
        rt.execute("UPDATE metacog_observations SET status = ? WHERE id = ?",
                   (self._action, self._id))
        rt.commit()
        rt.close()
        applied = None
        if self._action == "accepted" and row["suggestion"]:
            applied = TuneConfig(self._settings, json.loads(row["suggestion"]),
                                 self._notify, source="metacog",
                                 note=f"observação #{self._id} aceita"
                                 ).execute()
        self._notify("metacog.reviewed", {"id": self._id,
                                          "action": self._action,
                                          "applied": bool(applied)})
        return {"id": self._id, "status": self._action,
                "applied": applied and {"history_id": applied["history_id"],
                                        "trace_id": applied["trace_id"]}}
