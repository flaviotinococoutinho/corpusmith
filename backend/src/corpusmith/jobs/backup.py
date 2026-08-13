"""Job `backup` (P-14): o backup verificável passa a ser AUTOMÁTICO.

Três decisões, na ordem em que importam:
- o run VERIFICA cada sha256 do zip recém-criado — backup automático que
  ninguém confere é fé, não durabilidade;
- a retenção (`keep`, default 4) poda os antigos SÓ depois de o novo
  verificar: um zip inválido nunca justifica apagar o anterior válido;
- a quiescência exclui o PRÓPRIO job (ele roda leased dentro do worker;
  sem isso, todo backup agendado esperaria o timeout inteiro).
"""
from __future__ import annotations
from pathlib import Path
from ..settings import Settings
from ..usecases.backup_restore import CreateBackup, list_backups, verify_backup


def run(s: Settings, payload: dict, emit) -> dict:
    created = CreateBackup(
        s, notify=emit,
        exclude_job=getattr(emit, "job_id", None)).execute()
    verify = verify_backup(created["path"])
    result = {**created, "verify": verify, "pruned": 0}
    if not verify["ok"]:
        emit("backup.verify_failed", {"path": created["path"],
                                      "corrupted": verify["corrupted"],
                                      "missing": verify["missing"]})
        return result
    keep = int(payload.get("keep", s.get("backup.keep", 4)))
    old = [b["path"] for b in list_backups(s)][:-keep] if keep > 0 else []
    for path in old:
        Path(path).unlink(missing_ok=True)
        result["pruned"] += 1
    return result
