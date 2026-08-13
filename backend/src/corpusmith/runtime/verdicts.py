"""Registro de vereditos sobre padrão — a casca de `kernel/verdicts.py`.

Mora em `runtime.db` e a escolha é a substância, pela mesma razão dos
checkpoints (ADR-46): `index.db` é reconstruível e o job `leiden` recria
`graph_bridges` do zero. Um veredito humano guardado lá seria apagado pela
própria recomputação que ele existe para calar — o item rejeitado voltaria na
execução seguinte, e o usuário concluiria (com razão) que o produto não
escuta.
"""
from __future__ import annotations
import json
import time
from ..kernel.verdicts import STATUS, Verdict, pattern_key, suprimidos
from .db import connect

__all__ = ["record", "load", "suppressed_keys", "pattern_key", "Verdict"]


def record(settings, kind: str, pages, status: str, *,
           until: float | None = None, note: str = "") -> Verdict:
    """Registra o juízo humano sobre um padrão. Idempotente por (kind, key).

    Recusa status fora do vocabulário fechado: um `status` livre viraria
    filtro que ninguém sabe interpretar seis meses depois."""
    if status not in STATUS:
        raise ValueError(f"status inválido: {status!r} — aceitos: {STATUS}")
    key = pattern_key(pages)
    agora = time.time()
    ordenadas = sorted(set(pages))
    rt = connect(settings.app_support / "runtime.db")
    try:
        rt.execute(
            "INSERT INTO pattern_verdicts(kind, key, status, until, pages, "
            "note, decided_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(kind, key) DO UPDATE SET status=excluded.status, "
            "until=excluded.until, note=excluded.note, "
            "decided_at=excluded.decided_at",
            (kind, key, status, until, json.dumps(ordenadas), note, agora))
        rt.commit()
    finally:
        rt.close()
    return Verdict(kind, key, status, until, tuple(ordenadas), note, agora)


def load(settings, kind: str | None = None) -> list[Verdict]:
    rt = connect(settings.app_support / "runtime.db")
    try:
        sql = ("SELECT kind, key, status, until, pages, note, decided_at "
               "FROM pattern_verdicts")
        linhas = [dict(r) for r in (rt.execute(sql + " WHERE kind=?", (kind,))
                                    if kind else rt.execute(sql))]
    except Exception:                                    # noqa: BLE001
        return []                    # banco anterior à migração: sem vereditos
    finally:
        rt.close()
    return [Verdict(r["kind"], r["key"], r["status"], r["until"],
                    tuple(json.loads(r["pages"])), r["note"] or "",
                    r["decided_at"]) for r in linhas]


def suppressed_keys(settings, kind: str) -> set[str]:
    """Chaves que as fontes da fila devem pular AGORA (o `until` decide)."""
    return suprimidos(load(settings, kind), time.time())
