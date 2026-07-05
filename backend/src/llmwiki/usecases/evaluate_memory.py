"""EvaluateMemory (v0.8 §10 como use case): LongMemEval local — mede o
SISTEMA de memória (retrieval + temporal + abstenção), não o modelo."""
from __future__ import annotations
import json
import re
from .ask_memory import AskMemory
from .base import UseCase
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
        stats: dict[str, list[int]] = {}
        details = []
        for line in gold.read_text().splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            response = AskMemory(self._settings, case["q"], local_only=True,
                                 as_of=case.get("as_of")).execute()
            passed = self._grade(case, response)
            category = case["category"]
            total, ok = stats.get(category, [0, 0])
            stats[category] = [total + 1, ok + int(passed)]
            details.append({"q": case["q"], "category": category,
                            "ok": passed})
        self._persist(stats, details)
        self._notify("eval.done", {"stats": {c: f"{p}/{t}"
                                             for c, (t, p) in stats.items()}})
        return {"stats": stats}

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

    def _persist(self, stats, details) -> None:
        rt = connect(self._settings.app_support / "runtime.db")
        for category, (total, passed) in stats.items():
            rt.execute("INSERT INTO eval_runs(category, total, passed, detail) "
                       "VALUES (?,?,?,?)",
                       (category, total, passed,
                        json.dumps([d for d in details
                                    if d["category"] == category])))
        rt.commit()
        rt.close()
