"""Seed do golden eval (QA-1, v1.6.3): distribui páginas avaliáveis e o
`bundle/harness/golden_eval.jsonl` — o eval deixa de ser no-op
out-of-the-box.

Idempotente e não-destrutivo (contrato do `corpusmith seed`): página que já
existe NUNCA é reescrita; golden existente (possivelmente curado pelo
usuário) NUNCA é sobrescrito. Páginas entram pelo BundleWriter (Harness,
INV-DATA-001); o golden — dataset, não página canônica — é escrito no
bundle e commitado pelo GitStore para o repo do kb ficar limpo."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from ..okf.document import OKFDocument, OKFFrontMatter
from ..okf.git_store import GitStore
from ..okf.writer import BundleWriter
from ..retrieval.fts import rebuild_index
from ..settings import Settings

_SEED = Path(__file__).resolve().parents[3] / "db" / "seeds" \
    / "golden_eval_seed.json"


def seed_golden_eval(settings: Settings,
                     seed_file: Path | None = None) -> dict:
    data = json.loads((seed_file or _SEED).read_text())
    kb = settings.path("knowledge")
    bundle = kb / "bundle"
    docs = []
    for page in data["pages"]:
        if (bundle / page["rel_path"]).exists():
            continue                       # nunca reescreve página do usuário
        docs.append(OKFDocument(
            rel_path=page["rel_path"], body=page["body"],
            meta=OKFFrontMatter(
                type=page["type"], title=page["title"],
                timestamp=datetime.now(timezone.utc),
                valid_at=page.get("valid_at"),
                invalid_at=page.get("invalid_at"),
                **{"privacy": page["privacy"],
                   "generated_via": "human:seed"})))
    written = 0
    if docs:
        BundleWriter(kb).write(docs, log_kind="Creation",
                               log_message="golden eval seed (QA-1)",
                               commit_message="seed: páginas do golden eval")
        written = len(docs)
    golden = bundle / "harness" / "golden_eval.jsonl"
    cases = 0
    if not golden.exists():                # nunca sobrescreve golden curado
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text("\n".join(
            json.dumps(c, ensure_ascii=False) for c in data["cases"]) + "\n")
        GitStore(kb).commit("seed: golden_eval.jsonl")
        cases = len(data["cases"])
    if written or cases:
        rebuild_index(settings)            # respondível JÁ (como no promote)
    return {"pages": written, "cases": cases}
