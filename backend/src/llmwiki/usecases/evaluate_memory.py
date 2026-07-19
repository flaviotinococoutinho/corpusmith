"""EvaluateMemory (v0.8 §10 como use case): LongMemEval local — mede o
SISTEMA de memória (retrieval + temporal + abstenção), não o modelo.

v1.6 (ADR-38): cada execução produz Generalization Envelopes — o
CONTEXTO exato da avaliação (dataset+hash, amostra, categorias, HEAD do
bundle, versão do produto) — para os mecanismos cujo contrato em
epistemics.toml declara evaluated_by=["eval_memory"]. Amostra abaixo de
epistemics.min_sample ⇒ partially_evaluated (regra pura envelope_status).
A avaliação usa golden set + desfecho determinístico: evidência
INDEPENDENTE do mecanismo avaliado (não-autocertificação).
"""
from __future__ import annotations
import hashlib
import json
import re
import uuid
from .ask_memory import AskMemory
from .base import UseCase
from .. import __version__
from ..epistemic import envelope_status
from ..epistemic.model import EvaluationEnvelope
from ..runtime.db import connect
from ..settings import Settings


class EvaluateMemory(UseCase):
    def __init__(self, settings: Settings, notify=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        gold = self._settings.path("knowledge") / "bundle" / "harness" \
            / "golden_eval.jsonl"
        if not gold.exists():
            return {"skipped": "golden_eval.jsonl ausente"}
        gold_text = gold.read_text()
        stats: dict[str, list[int]] = {}
        details = []
        as_ofs: list[str] = []
        ranked_metrics: list[dict] = []
        for line in gold_text.splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            response = AskMemory(self._settings, case["q"], local_only=True,
                                 as_of=case.get("as_of")).execute()
            passed = self._grade(case, response)
            category = case["category"]
            total, ok = stats.get(category, [0, 0])
            stats[category] = [total + 1, ok + int(passed)]
            if case.get("as_of"):
                as_ofs.append(str(case["as_of"]))
            case_metrics = self._rank_metrics(case, response)
            if case_metrics:
                ranked_metrics.append(case_metrics)
            details.append({"q": case["q"], "category": category,
                            "ok": passed, "metrics": case_metrics})
        metrics = self._aggregate(ranked_metrics)
        run_ids = self._persist(stats, details)
        envelopes = self._persist_envelopes(gold_text, stats, as_ofs,
                                            run_ids, metrics)
        self._notify("eval.done", {"stats": {c: f"{p}/{t}"
                                             for c, (t, p) in stats.items()}})
        return {"stats": stats, "metrics": metrics, "envelopes": envelopes}

    @staticmethod
    def _grade(case: dict, response: dict) -> bool:
        if case.get("expect_abstain"):
            return bool(response.get("abstained"))
        ok = not response.get("abstained", False)
        got = {e["page"] for e in response.get("evidence", [])}
        if case.get("expect_pages"):
            ok &= bool(set(case["expect_pages"]) & got)          # recall@5
        if case.get("expect_regex") and response.get("answer"):
            ok &= bool(re.search(case["expect_regex"], response["answer"]))
        return ok

    @staticmethod
    def _rank_metrics(case: dict, response: dict) -> dict | None:
        """QA-1 (v1.6.3): métricas FRACIONÁRIAS por caso com expect_pages —
        recall@5 (fração das páginas esperadas presentes) e MRR (1/rank da
        primeira esperada) — o passa/não-passa esconde a qualidade do rank."""
        expected = case.get("expect_pages")
        if not expected:
            return None
        ranked = [e["page"] for e in response.get("evidence", [])]
        recall = len(set(expected) & set(ranked)) / len(expected)
        reciprocal = 0.0
        for position, page in enumerate(ranked):
            if page in expected:
                reciprocal = 1.0 / (position + 1)
                break
        return {"recall_at_5": round(recall, 4), "mrr": round(reciprocal, 4)}

    @staticmethod
    def _aggregate(ranked: list[dict]) -> dict:
        if not ranked:
            return {"graded_cases": 0}
        n = len(ranked)
        return {"graded_cases": n,
                "mean_recall_at_5": round(
                    sum(m["recall_at_5"] for m in ranked) / n, 4),
                "mean_mrr": round(sum(m["mrr"] for m in ranked) / n, 4)}

    def _persist(self, stats, details) -> list[int]:
        rt = connect(self._settings.app_support / "runtime.db")
        run_ids = []
        for category, (total, passed) in stats.items():
            cursor = rt.execute(
                "INSERT INTO eval_runs(category, total, passed, detail) "
                "VALUES (?,?,?,?)",
                (category, total, passed,
                 json.dumps([d for d in details
                             if d["category"] == category])))
            run_ids.append(cursor.lastrowid)
        rt.commit()
        rt.close()
        return run_ids

    # ------------------------------- Generalization Envelope (v1.6)
    def _covered_mechanisms(self) -> tuple[list, str]:
        """Contratos que declaram esta avaliação como fonte de evidência
        (+ versão do registro para o envelope). Registro ausente/inválido
        ⇒ nenhum envelope (falha graciosa)."""
        try:
            from ..harness.epistemics import load_registry
            registry, _ = load_registry()
        except Exception:
            return [], "?"
        return ([c for c in registry.contracts
                 if "eval_memory" in c.evaluated_by], registry.version)

    def _bundle_head(self) -> str:
        try:
            idx = connect(self._settings.app_support / "index.db")
            row = idx.execute("SELECT value FROM index_meta "
                              "WHERE key='bundle_head'").fetchone()
            idx.close()
            return row["value"] if row else ""
        except Exception:
            return ""

    def _policy_version(self, rt) -> str:
        row = rt.execute("SELECT id FROM config_history "
                         "ORDER BY id DESC LIMIT 1").fetchone()
        return f"config#{row['id']}" if row else "baseline"

    def _persist_envelopes(self, gold_text: str, stats: dict,
                           as_ofs: list[str], run_ids: list[int],
                           rank_metrics: dict | None = None) -> list[dict]:
        contracts, registry_version = self._covered_mechanisms()
        if not contracts:
            return []
        sample = sum(t for t, _ in stats.values())
        min_sample = int(self._settings.get("epistemics.min_sample", 20))
        status = envelope_status(sample, min_sample=min_sample)
        metrics = {f"{c}_pass_rate": round(p / t, 4)
                   for c, (t, p) in sorted(stats.items()) if t}
        metrics["overall_pass_rate"] = round(
            sum(p for _, p in stats.values()) / sample, 4) if sample else 0.0
        for key, value in (rank_metrics or {}).items():
            metrics[key] = value           # QA-1: recall@5/MRR no envelope
        temporal = f"{min(as_ofs)}..{max(as_ofs)}" if as_ofs else ""
        rt = connect(self._settings.app_support / "runtime.db")
        policy = self._policy_version(rt)
        written = []
        for contract in contracts:
            envelope = EvaluationEnvelope(
                mechanism_id=contract.mechanism_id,
                contract_version=registry_version,
                policy_version=policy,
                product_version=__version__,
                bundle_head=self._bundle_head(),
                dataset="golden_eval.jsonl",
                dataset_sha256=hashlib.sha256(
                    gold_text.encode()).hexdigest(),
                sample_size=sample,
                query_categories=tuple(sorted(stats)),
                temporal_range=temporal,
                metrics=tuple(sorted(metrics.items())),
                known_exclusions=(
                    "idiomas ausentes do golden set",
                    "perguntas fora do bundle",),
                out_of_scope=tuple(s.text for s in contract.validity_scope),
                eval_run_ids=tuple(run_ids),
                evaluation_status=status)
            data = envelope.to_dict()
            rt.execute(
                "INSERT INTO evaluation_envelopes(id, mechanism_id, "
                "contract_version, policy_version, product_version, "
                "bundle_head, dataset, dataset_sha256, sample_size, "
                "query_categories, languages, domains, temporal_range, "
                "metrics, confidence_intervals, known_exclusions, "
                "out_of_scope, eval_run_ids, evaluation_status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, data["mechanism_id"],
                 data["contract_version"], data["policy_version"],
                 data["product_version"], data["bundle_head"],
                 data["dataset"], data["dataset_sha256"],
                 data["sample_size"], json.dumps(data["query_categories"]),
                 json.dumps(data["languages"]), json.dumps(data["domains"]),
                 data["temporal_range"], json.dumps(data["metrics"]),
                 None, json.dumps(data["known_exclusions"]),
                 json.dumps(data["out_of_scope"]),
                 json.dumps(data["eval_run_ids"]),
                 data["evaluation_status"]))
            written.append({"mechanism_id": contract.mechanism_id,
                            "status": data["evaluation_status"],
                            "sample_size": sample})
        rt.commit()
        rt.close()
        return written


def envelopes_for(settings: Settings, mechanism_id: str,
                  limit: int = 20) -> list[dict]:
    """Leitura dos envelopes persistidos (CLI/facade/API — mesma fonte)."""
    rt = connect(settings.app_support / "runtime.db")
    rows = rt.execute(
        "SELECT * FROM evaluation_envelopes WHERE mechanism_id = ? "
        "ORDER BY created_at DESC LIMIT ?", (mechanism_id, limit)).fetchall()
    rt.close()
    out = []
    for r in rows:
        d = dict(r)
        for key in ("query_categories", "languages", "domains",
                    "known_exclusions", "out_of_scope", "eval_run_ids"):
            d[key] = json.loads(d[key] or "[]")
        d["metrics"] = json.loads(d["metrics"] or "{}")
        d["confidence_intervals"] = json.loads(
            d["confidence_intervals"] or "null")
        out.append(d)
    return out
