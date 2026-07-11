"""Configuração de negócio versionada (v0.16) — a config vira LINHAGEM.

Sistemas evolutivos, transposição honesta: cada ajuste é uma variação;
o guard de fitness (validação de tipo/domínio + probe pós-aplicação)
seleciona; o `config_history` (ring buffer de 30 no runtime.db) é a
linhagem — a vigente é sempre a linha mais recente. Deu problema?
`RollbackConfig` reaplica o snapshot ANTERIOR: retornar de geração é
O(1) porque cada linha carrega o estado completo, não só o delta.

O overrides.yaml continua sendo o mecanismo de persistência que o
`Settings.load()` reaplica no boot (o banco não é lido no boot — a
fonte de verdade do estado vigente segue sendo o Settings vivo +
overrides.yaml; o banco é a MEMÓRIA dos estados, com identidade
snowflake por ajuste para o tracing ponta a ponta).
"""
from __future__ import annotations
import json
from .base import UseCase
from ..kernel.identity import SnowflakeFactory
from ..runtime.db import connect
from ..settings import Settings

HISTORY_LIMIT = 30
_IDS = SnowflakeFactory("config")


def config_history(settings: Settings, limit: int = HISTORY_LIMIT) -> list[dict]:
    rt = connect(settings.app_support / "runtime.db")
    rows = rt.execute(
        "SELECT id, ts, trace_id, changes, snapshot, source, note "
        "FROM config_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    rt.close()
    return [{**dict(r), "changes": json.loads(r["changes"]),
             "snapshot": json.loads(r["snapshot"])} for r in rows]


def _record(settings: Settings, changes: dict, source: str,
            note: str | None) -> dict:
    """Insere a linha e PODA o ring: nunca mais que HISTORY_LIMIT."""
    trace_id = _IDS.next_rendered()
    rt = connect(settings.app_support / "runtime.db")
    cur = rt.execute(
        "INSERT INTO config_history(trace_id, changes, snapshot, source, note) "
        "VALUES (?,?,?,?,?)",
        (trace_id, json.dumps(changes, sort_keys=True),
         json.dumps(settings.snapshot(), sort_keys=True), source, note))
    rt.execute("DELETE FROM config_history WHERE id NOT IN "
               "(SELECT id FROM config_history ORDER BY id DESC LIMIT ?)",
               (HISTORY_LIMIT,))
    rt.commit()
    history_id = cur.lastrowid
    rt.close()
    return {"history_id": history_id, "trace_id": trace_id}


class TuneConfig(UseCase):
    """Ajuste a quente COM guard de fitness. Três linhas de defesa:
    1. validação de tipo/domínio ANTES de tocar o estado (variação
       inviável nem nasce);
    2. probe pós-aplicação (round-trip do modelo Settings) — se o
       conjunto aplicado for inconsistente, REVERTE sozinho para o
       snapshot anterior e registra a linha de rollback;
    3. a linhagem no banco — o RollbackConfig manual cobre problemas
       que só aparecem depois (jobs falhando, retrieval degradado)."""

    def __init__(self, settings: Settings, changes: dict, notify=None, *,
                 source: str = "cockpit", note: str | None = None):
        self._settings = settings
        self._changes = changes
        self._notify = notify or (lambda *a, **k: None)
        self._source = source
        self._note = note

    def execute(self) -> dict:
        previous = self._settings.snapshot()
        self._validate(previous)
        self._baseline(previous)
        self._settings.tune(self._changes)
        try:
            Settings(**self._settings.model_dump(mode="python"))  # probe
        except Exception as e:
            self._settings.tune(previous)          # fitness reprovou: reverte
            _record(self._settings, previous, "rollback",
                    f"auto: probe falhou ({e})")
            self._notify("config.rolled_back", {"reason": str(e)})
            raise ValueError(f"ajuste revertido — probe falhou: {e}")
        record = _record(self._settings, self._changes,
                         self._source, self._note)
        self._notify("config.tuned", {"sections": sorted(self._changes),
                                      **record})
        return {"snapshot": self._settings.snapshot(), **record}

    def _validate(self, previous: dict) -> None:
        for section, values in self._changes.items():
            if section not in Settings.TUNABLE_SECTIONS:
                raise ValueError(f"seção não ajustável: {section}")
            if not isinstance(values, dict):
                raise ValueError(f"{section}: esperado objeto")
            for key, value in values.items():
                current = previous[section].get(key)
                if current is None:
                    if section == "flags" and isinstance(value, bool):
                        continue                    # flags novas: só booleanas
                    raise ValueError(f"chave desconhecida: {section}.{key}")
                if isinstance(current, bool) != isinstance(value, bool):
                    raise ValueError(f"{section}.{key}: esperado booleano"
                                     if isinstance(current, bool) else
                                     f"{section}.{key}: booleano não cabe aqui")
                if isinstance(current, (int, float)) \
                        and not isinstance(current, bool):
                    if not isinstance(value, (int, float)) \
                            or isinstance(value, bool):
                        raise ValueError(f"{section}.{key}: esperado número")

    def _baseline(self, previous: dict) -> None:
        """Primeira mutação de um banco virgem grava a geração-zero —
        sem ela o primeiro rollback não teria para onde voltar."""
        rt = connect(self._settings.app_support / "runtime.db")
        empty = rt.execute(
            "SELECT COUNT(*) c FROM config_history").fetchone()["c"] == 0
        rt.close()
        if empty:
            _record(self._settings, {}, "baseline", "estado pré-ajustes")


class RollbackConfig(UseCase):
    """Retorna à configuração ANTERIOR à vigente (a penúltima linha do
    ring) e registra o retorno como nova geração — a linhagem nunca anda
    para trás, o estado sim."""

    def __init__(self, settings: Settings, notify=None):
        self._settings = settings
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        rows = config_history(self._settings, limit=2)
        if len(rows) < 2:
            raise ValueError("sem configuração anterior para retornar")
        target = rows[1]
        self._settings.tune(target["snapshot"])
        record = _record(self._settings, target["snapshot"], "rollback",
                         f"manual → #{target['id']} ({target['trace_id']})")
        self._notify("config.rolled_back", {"to": target["id"], **record})
        return {"snapshot": self._settings.snapshot(),
                "restored": target["id"], **record}
