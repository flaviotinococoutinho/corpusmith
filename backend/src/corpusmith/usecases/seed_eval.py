"""Seed do golden eval (QA-1, v1.6.3): distribui páginas avaliáveis e o
`bundle/harness/golden_eval.jsonl` — o eval deixa de ser no-op
out-of-the-box.

Idempotente e não-destrutivo (contrato do `corpusmith seed`): página que já
existe NUNCA é reescrita; golden existente (possivelmente curado pelo
usuário) NUNCA é sobrescrito. Páginas entram pelo BundleWriter (Harness,
INV-DATA-001) — e o golden também, desde o ADR-61: antes ele era escrito
com `write_text` e commitado por `GitStore.commit` (`git add -A`), a única
escrita no bundle fora do escritor — sem lock, sem `log.md`, sem validação,
e levando para o commit "seed: golden" qualquer sujeira do kb (Q-28). Agora
passa por `BundleWriter.write_artifact`: gate de artefato, lock, log e um
commit que leva só o golden e o log; "nunca sobrescrever" é decidido
dentro do lock."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from ..harness.artifacts import GOLDEN_EVAL
from ..okf.document import OKFDocument, OKFFrontMatter
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
    texto = "\n".join(json.dumps(c, ensure_ascii=False)
                      for c in data["cases"]) + "\n"
    golden = BundleWriter(kb).write_artifact(
        GOLDEN_EVAL, texto, create_only=True,  # nunca sobrescreve golden curado
        log_kind="Creation",
        log_message=f"golden eval (QA-1): {GOLDEN_EVAL}, "
                    f"{len(data['cases'])} caso(s)",
        commit_message="seed: golden_eval.jsonl")
    cases = 0 if golden.get("skipped") else len(data["cases"])
    if written or cases:
        rebuild_index(settings)            # respondível JÁ (como no promote)
    return {"pages": written, "cases": cases}
