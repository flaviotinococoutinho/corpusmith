"""RecordOutcome (v0.9): o desfecho do usuário fecha DOIS laços.

1. ask_outcomes → heat/overlay (reflect, v0.8);
2. Hedge sobre os streams (kernel.information.hedge): via ask_provenance
   sabemos QUAL stream trouxe cada evidência julgada — useful é ganho,
   dead_end/corrected é perda; os pesos em stream_weights realimentam a
   fusão RRF das próximas consultas (expert weighting com clamp).

Correção com nota vira memória nova no inbox (raw/correcoes/).
"""
from __future__ import annotations
import json
import time
from .base import UseCase
from ..kernel.information import hedge
from ..runtime.db import connect
from ..settings import Settings

VERDICTS = ("useful", "dead_end", "corrected")


class RecordOutcome(UseCase):
    def __init__(self, settings: Settings, *, verdict: str,
                 ask_id: str | None = None, note: str | None = None,
                 pages: list[str] | None = None):
        if verdict not in VERDICTS:
            raise ValueError(f"verdict inválido: {verdict}")
        self._settings = settings
        self._verdict = verdict
        self._ask_id = ask_id
        self._note = note
        self._pages = pages or []

    def execute(self) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        rt.execute("INSERT INTO ask_outcomes(ask_id, verdict, note, pages) "
                   "VALUES (?,?,?,?)",
                   (self._ask_id, self._verdict, self._note,
                    json.dumps(self._pages)))
        self._update_stream_credit(rt)
        rt.commit()
        rt.close()
        if self._verdict == "corrected" and self._note:
            self._capture_correction()
        return {"ok": True}

    def _update_stream_credit(self, rt) -> None:
        if not self._ask_id or not self._pages:
            return
        placeholders = ",".join("?" * len(self._pages))
        contributing = {r["stream"] for r in rt.execute(
            f"SELECT DISTINCT stream FROM ask_provenance "
            f"WHERE ask_id=? AND page IN ({placeholders})",
            (self._ask_id, *self._pages))}
        if not contributing:
            return
        current = {r["stream"]: r["weight"] for r in
                   rt.execute("SELECT stream, weight FROM stream_weights")}
        for stream in contributing:
            current.setdefault(stream, 1.0)
        loss = -1.0 if self._verdict == "useful" else 1.0
        updated = hedge(current, {s: loss for s in contributing})
        for stream, weight in updated.items():
            rt.execute("INSERT INTO stream_weights(stream, weight) "
                       "VALUES (?,?) ON CONFLICT(stream) "
                       "DO UPDATE SET weight=?", (stream, weight, weight))

    def _capture_correction(self) -> None:
        kb = self._settings.path("knowledge")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = kb / "raw" / "correcoes" / f"{stamp}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        subject = self._pages[0] if self._pages else "consulta"
        target.write_text(f"# Correção sobre {subject}\n\n{self._note}\n")
