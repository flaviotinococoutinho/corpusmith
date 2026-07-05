"""Registry de jobs — contrato único: run(settings, payload, emit) -> dict."""
from __future__ import annotations
from . import (ask, compile as compile_job, consolidate, embed, leiden,
               lora, ocr, reconcile, reflect, rerank, review)
from ..harness import eval_memory
from ..retrieval.fts import rebuild_index


def _index(s, payload, emit):
    return rebuild_index(s)


REGISTRY = {
    "compile_source": compile_job.run,
    "consolidate_inbox": consolidate.run,
    "ask": ask.run,
    "embed": embed.run,
    "rerank": rerank.run,
    "leiden": leiden.run,
    "ocr": ocr.run,
    "lora_train": lora.run,
    "review_weekly": review.run,
    "reflect": reflect.run,
    "eval_memory": eval_memory.run,
    "index_rebuild": _index,
}
