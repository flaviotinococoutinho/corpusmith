#!/usr/bin/env python3
"""Bench rápido (Parte V §1.3): mede lint, index e busca FTS no bundle atual."""
from __future__ import annotations
import time
from llmwiki.harness.runner import HarnessRunner
from llmwiki.okf.bundle import BundleReader
from llmwiki.okf.git_store import GitStore
from llmwiki.retrieval.fts import rebuild_index, search
from llmwiki.settings import Settings


def timed(label, fn):
    t0 = time.perf_counter()
    out = fn()
    print(f"{label:20s} {time.perf_counter() - t0:8.3f}s  {out}")


def main():
    s = Settings.load()
    kb = s.path("knowledge")
    reader = BundleReader(kb / "bundle")
    runner = HarnessRunner(reader, GitStore(kb))
    timed("lint_bundle", lambda: len(runner.lint_bundle(kb / "bundle")))
    timed("rebuild_index", lambda: rebuild_index(s))
    timed("fts.search", lambda: len(search(s, "arquitetura decisão")))


if __name__ == "__main__":
    main()
