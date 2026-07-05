"""Eval de memória (v0.8 §10) — LongMemEval do projeto: mede o SISTEMA de
memória (retrieval + temporal + abstenção), não o modelo. Roda o /ask
LOCAL-only contra bundle/harness/golden_eval.jsonl e grava recall/aprovação
por categoria (extract · multi_session · temporal · update · abstain)."""
from __future__ import annotations
import json
import re
from ..runtime.db import connect
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    from ..jobs.ask import answer_local          # entrada programática do ask
    gold = s.path("knowledge") / "bundle" / "harness" / "golden_eval.jsonl"
    if not gold.exists():
        return {"skipped": "golden_eval.jsonl ausente"}
    stats: dict[str, list[int]] = {}
    details = []
    for line in gold.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        r = answer_local(s, case["q"], as_of=case.get("as_of"), k=5)
        ok = True
        if case.get("expect_abstain"):
            ok = bool(r.get("abstained"))
        else:
            got = {e["page"] for e in r.get("evidence", [])}
            if case.get("expect_pages"):
                ok &= bool(set(case["expect_pages"]) & got)     # recall@5
            if case.get("expect_regex") and r.get("answer"):
                ok &= bool(re.search(case["expect_regex"], r["answer"]))
            ok &= not r.get("abstained", False)
        cat = case["category"]
        t, p = stats.get(cat, [0, 0])
        stats[cat] = [t + 1, p + int(ok)]
        details.append({"q": case["q"], "category": cat, "ok": ok})
    rt = connect(s.app_support / "runtime.db")
    for cat, (t, p) in stats.items():
        rt.execute("INSERT INTO eval_runs(category, total, passed, detail) "
                   "VALUES (?,?,?,?)", (cat, t, p,
                   json.dumps([d for d in details if d["category"] == cat])))
    rt.commit()
    rt.close()
    emit("eval.done", {"stats": {c: f"{p}/{t}" for c, (t, p) in stats.items()}})
    return {"stats": stats}
