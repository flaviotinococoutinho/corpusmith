"""Pipelines configuráveis (v0.17) — a orquestração vira DADO.

Um pipeline é um spec declarativo (nome + estágios) guardado no
runtime.db; cada estágio referencia um job já registrado e roda em
sequência, com política de erro própria (`stop`/`continue`) e passagem
de resultado (`"$prev.chave"` no payload puxa do estágio anterior).

Invariante epistêmico preservado: o pipeline orquestra ACIMA do
Template Method — os estágios são os MESMOS jobs de sempre (sanduíche,
reconciliação e gate acontecem dentro deles); configurar um pipeline
não abre nenhuma porta para escrever página fora do trilho.

Dependency Inversion: o use case NÃO importa o registry de jobs (camada
adapter) — recebe `registry: Mapping[nome → handler]` de quem o chama
(`jobs/pipeline.py` injeta o REGISTRY real; testes injetam fakes).
Validação em dois tempos: estrutural ao salvar (sem registry) e de
existência dos jobs ao rodar (fail-fast antes do primeiro estágio).
"""
from __future__ import annotations
import json
import re
import time
from typing import Callable, Mapping
from .base import UseCase
from ..kernel.identity import factory as id_factory
from ..runtime.db import connect
from ..settings import Settings

RUNS_KEPT = 200
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
_ON_ERROR = ("stop", "continue")
_IDS = id_factory("pipeline")

DEFAULT_PIPELINES = {
    "absorver-inbox": {
        "description": "Consolida recorrências do inbox, reindexa e "
                       "recalcula comunidades/pontes.",
        "stages": [
            {"job": "consolidate_inbox"},
            {"job": "index_rebuild"},
            {"job": "leiden", "on_error": "continue"},
        ]},
    "manutencao-semanal": {
        "description": "Reflect (heat/overlay) → revisão semanal → eval "
                       "de memória em 5 categorias.",
        "stages": [
            {"job": "reflect"},
            {"job": "review_weekly", "on_error": "continue"},
            {"job": "eval_memory", "on_error": "continue"},
        ]},
    "qualidade-total": {
        "description": "Reindexa do zero, recomputa topologia e mede a "
                       "memória — o check-up completo.",
        "stages": [
            {"job": "index_rebuild"},
            {"job": "leiden", "on_error": "continue"},
            {"job": "eval_memory", "on_error": "continue"},
        ]},
}


def validate_spec(name: str, spec: dict) -> None:
    """Validação ESTRUTURAL (sem registry — jobs conferidos no run)."""
    if not _NAME.match(name or ""):
        raise ValueError("nome deve ser slug [a-z0-9-], até 60 chars")
    stages = spec.get("stages")
    if not isinstance(stages, list) or not 1 <= len(stages) <= 20:
        raise ValueError("stages: lista de 1 a 20 estágios")
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict) or not isinstance(stage.get("job"), str):
            raise ValueError(f"estágio {i}: esperado objeto com 'job'")
        if stage["job"] == "pipeline":
            raise ValueError(f"estágio {i}: pipeline dentro de pipeline "
                             "não é permitido (sem recursão)")
        if stage.get("on_error", "stop") not in _ON_ERROR:
            raise ValueError(f"estágio {i}: on_error ∈ {_ON_ERROR}")
        if not isinstance(stage.get("payload", {}), dict):
            raise ValueError(f"estágio {i}: payload deve ser objeto")


def list_pipelines(settings: Settings) -> list[dict]:
    rt = connect(settings.app_support / "runtime.db")
    rows = rt.execute("SELECT name, spec, builtin FROM pipelines "
                      "ORDER BY builtin DESC, name").fetchall()
    last = {r["pipeline"]: dict(r) for r in rt.execute(
        "SELECT pipeline, state, trace_id, finished_at, "
        "MAX(started_at) started_at FROM pipeline_runs GROUP BY pipeline")}
    rt.close()
    return [{"name": r["name"], "builtin": bool(r["builtin"]),
             **json.loads(r["spec"]),
             "last_run": last.get(r["name"])} for r in rows]


def pipeline_runs(settings: Settings, name: str | None = None,
                  limit: int = 20) -> list[dict]:
    rt = connect(settings.app_support / "runtime.db")
    where, params = ("WHERE pipeline = ?", [name]) if name else ("", [])
    rows = rt.execute(
        f"SELECT id, pipeline, trace_id, state, stages, started_at, "
        f"finished_at FROM pipeline_runs {where} "
        f"ORDER BY id DESC LIMIT ?", (*params, limit)).fetchall()
    rt.close()
    return [{**dict(r), "stages": json.loads(r["stages"])} for r in rows]


def seed_default_pipelines(settings: Settings) -> None:
    """Idempotente: garante os builtin sem tocar nos editados/criados."""
    rt = connect(settings.app_support / "runtime.db")
    for name, spec in DEFAULT_PIPELINES.items():
        rt.execute("INSERT OR IGNORE INTO pipelines(name, spec, builtin) "
                   "VALUES (?,?,1)", (name, json.dumps(spec)))
    rt.commit()
    rt.close()


class SavePipeline(UseCase):
    def __init__(self, settings: Settings, name: str, spec: dict):
        self._settings = settings
        self._name = name
        self._spec = {"description": spec.get("description", ""),
                      "stages": spec.get("stages")}

    def execute(self) -> dict:
        validate_spec(self._name, self._spec)
        rt = connect(self._settings.app_support / "runtime.db")
        rt.execute(
            "INSERT INTO pipelines(name, spec) VALUES (?,?) "
            "ON CONFLICT(name) DO UPDATE SET spec = excluded.spec, "
            "updated_at = unixepoch('subsec')",
            (self._name, json.dumps(self._spec)))
        rt.commit()
        rt.close()
        return {"name": self._name, **self._spec}


class DeletePipeline(UseCase):
    def __init__(self, settings: Settings, name: str):
        self._settings = settings
        self._name = name

    def execute(self) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        gone = rt.execute("DELETE FROM pipelines WHERE name = ?",
                          (self._name,)).rowcount
        rt.commit()
        rt.close()
        if not gone:
            raise KeyError(self._name)
        return {"deleted": self._name}


class RunPipeline(UseCase):
    """Executa um pipeline salvo (ou um spec inline) estágio a estágio.
    Todo run tem trace snowflake; todo estágio tem span; o filme fica em
    pipeline_runs e os eventos `pipeline.stage` saem ao vivo no SSE."""

    def __init__(self, settings: Settings, name: str,
                 registry: Mapping[str, Callable], notify=None, *,
                 spec: dict | None = None):
        self._settings = settings
        self._name = name
        self._registry = registry
        self._notify = notify or (lambda *a, **k: None)
        self._spec = spec

    def execute(self) -> dict:
        spec = self._spec or self._load()
        validate_spec(self._name, spec)
        missing = [s["job"] for s in spec["stages"]
                   if s["job"] not in self._registry]
        if missing:                              # fail-fast: nada roda pela metade
            raise ValueError(f"jobs desconhecidos no pipeline: {missing}")
        trace_id = _IDS.next_rendered()
        run_id = self._open_run(trace_id)
        stages_log: list[dict] = []
        prev_result: dict = {}
        failed = 0
        for index, stage in enumerate(spec["stages"]):
            span = _IDS.next_rendered()
            entry = {"job": stage["job"], "state": "running", "span": span}
            self._emit_stage(run_id, trace_id, index, entry)
            started = time.time()
            try:
                payload = self._resolve(stage.get("payload", {}), prev_result)
                result = self._registry[stage["job"]](
                    self._settings, payload, self._stage_emit(trace_id))
                prev_result = result if isinstance(result, dict) else {}
                entry.update(state="done",
                             ms=round(1000 * (time.time() - started)))
            except Exception as e:
                failed += 1
                prev_result = {}
                entry.update(state="failed", error=f"{type(e).__name__}: {e}",
                             ms=round(1000 * (time.time() - started)))
                if stage.get("on_error", "stop") == "stop":
                    stages_log.append(entry)
                    self._emit_stage(run_id, trace_id, index, entry)
                    return self._close_run(run_id, trace_id, "failed",
                                           stages_log)
            stages_log.append(entry)
            self._emit_stage(run_id, trace_id, index, entry)
        state = "partial" if failed else "done"
        return self._close_run(run_id, trace_id, state, stages_log)

    # ------------------------------------------------------------ helpers
    def _load(self) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        row = rt.execute("SELECT spec FROM pipelines WHERE name = ?",
                         (self._name,)).fetchone()
        rt.close()
        if not row:
            raise KeyError(f"pipeline desconhecido: {self._name}")
        return json.loads(row["spec"])

    @staticmethod
    def _resolve(payload: dict, prev: dict) -> dict:
        """Passagem de resultado: valor string `"$prev.chave"` vira o
        campo homônimo do resultado do estágio anterior (fail explícito
        se ausente — melhor que None silencioso)."""
        out = {}
        for key, value in payload.items():
            if isinstance(value, str) and value.startswith("$prev."):
                field = value[6:]
                if field not in prev:
                    raise ValueError(
                        f"payload.{key}: '{value}' ausente no resultado "
                        f"anterior (chaves: {sorted(prev)})")
                out[key] = prev[field]
            else:
                out[key] = value
        return out

    def _stage_emit(self, trace_id: str):
        def emit(type: str, data: dict | None = None):
            self._notify(type, {"trace_id": trace_id, **(data or {})})
        return emit

    def _emit_stage(self, run_id: int, trace_id: str, index: int,
                    entry: dict) -> None:
        self._notify("pipeline.stage",
                     {"pipeline": self._name, "run_id": run_id,
                      "trace_id": trace_id, "index": index, **entry})

    def _open_run(self, trace_id: str) -> int:
        rt = connect(self._settings.app_support / "runtime.db")
        cur = rt.execute("INSERT INTO pipeline_runs(pipeline, trace_id) "
                         "VALUES (?,?)", (self._name, trace_id))
        rt.execute("DELETE FROM pipeline_runs WHERE id NOT IN "
                   "(SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT ?)",
                   (RUNS_KEPT,))
        rt.commit()
        run_id = cur.lastrowid
        rt.close()
        return run_id

    def _close_run(self, run_id: int, trace_id: str, state: str,
                   stages_log: list[dict]) -> dict:
        rt = connect(self._settings.app_support / "runtime.db")
        rt.execute("UPDATE pipeline_runs SET state = ?, stages = ?, "
                   "finished_at = unixepoch('subsec') WHERE id = ?",
                   (state, json.dumps(stages_log), run_id))
        rt.commit()
        rt.close()
        self._notify("pipeline.done", {"pipeline": self._name,
                                       "run_id": run_id,
                                       "trace_id": trace_id,
                                       "state": state})
        return {"run_id": run_id, "trace_id": trace_id, "state": state,
                "stages": stages_log}
