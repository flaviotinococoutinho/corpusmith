#!/usr/bin/env python3
"""Wrapper do bench reprodutível (QA-2) — lógica em corpusmith/bench.py.

  bench.py                      # bundle sintético de 150 páginas + JSON
  bench.py --synthetic 500      # escala o sintético
  bench.py --current            # comportamento antigo: mede o bundle atual
  bench.py --json resultado.json
"""
from corpusmith.bench import main

if __name__ == "__main__":
    raise SystemExit(main())
