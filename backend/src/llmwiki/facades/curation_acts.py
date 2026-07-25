"""CurationActsFacade (F1-PR1) — a porta única dos atos humanos.

Em arquivo próprio de propósito: `CurationFacade` já tem ~20 métodos, e a
Fase 1 acrescenta sete atos. Empilhar tudo lá faria seis PRs disputarem o
mesmo arquivo (colisão mapeada em docs/15 §6).

Uma só entrada — `preview` e `act` sobre o registro fechado `ACTS` — de
modo que CLI, API e Cockpit resolvam ato por NOME sem cada um conhecer as
classes. Acrescentar um ato não muda esta facade.
"""
from __future__ import annotations
from ..settings import Settings
from ..usecases.curate import ACTS


class CurationActsFacade:
    def __init__(self, settings: Settings):
        self._settings = settings

    def kinds(self) -> list[str]:
        return sorted(ACTS)

    def preview(self, act: str, params: dict) -> dict:
        """CQS: levantamento puro, sem efeito nenhum."""
        return self._build(act, params).execute(dry_run=True)

    def act(self, act: str, params: dict, notify=None) -> dict:
        """Aplica. Levanta HarnessRejection quando o gate recusa — a API
        traduz em 422 legível; nunca 500."""
        return self._build(act, params, notify).execute(dry_run=False)

    def history(self, limit: int = 30) -> list[dict]:
        import json
        from ..runtime.db import connect
        rt = connect(self._settings.app_support / "runtime.db")
        rows = [dict(r) for r in rt.execute(
            "SELECT id, act, params, commit_sha, pages, created_at, "
            "undoes, undone_by FROM curation_acts "
            "ORDER BY id DESC LIMIT ?", (limit,))]
        rt.close()
        for row in rows:
            row["params"] = json.loads(row["params"] or "{}")
            row["pages"] = json.loads(row["pages"] or "[]")
        return rows

    def _build(self, act: str, params: dict, notify=None):
        if act not in ACTS:
            raise KeyError(f"ato desconhecido: {act}")
        return ACTS[act](self._settings, notify=notify, **params)
