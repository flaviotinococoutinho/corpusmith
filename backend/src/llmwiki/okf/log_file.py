"""`log.md` reservado — diário append-only do bundle (v0.6 §2.4).

Formato validado por `check_reserved_files` (headings `## YYYY-MM-DD`):

    # Log

    ## 2026-07-05

    * 14:02 [Creation] promovido de chat: Título da página
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

HEADER = "# Log\n"


class LogWriter:
    def __init__(self, bundle_root: Path):
        self.path = bundle_root / "log.md"

    def append(self, kind: str, message: str) -> None:
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        entry = f"* {now.strftime('%H:%M')} [{kind}] {message}"
        text = self.path.read_text() if self.path.exists() else HEADER
        day_h = f"## {day}"
        if day_h in text.splitlines():
            text = text.rstrip("\n") + f"\n{entry}\n"
        else:
            text = text.rstrip("\n") + f"\n\n{day_h}\n\n{entry}\n"
        self.path.write_text(text)
