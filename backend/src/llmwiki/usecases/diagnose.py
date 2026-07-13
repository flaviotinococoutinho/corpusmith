"""Doctor de invariantes (v1.4, backlog DATA-1) — verifica e REPARA.

Filosofia (Frente B do plano): o canônico é lei; as projeções se
curvam. O doctor NUNCA muta o bundle — só detecta divergência e, no
modo repair, reconstrói o que é reconstruível (o índice). Estado de
usuário (cognitivo, config) é reportado, nunca apagado automaticamente.

Invariantes verificados:
- INV-001: toda página no índice existe no bundle canônico;
- INV-002: o índice corresponde à revisão (HEAD) e à geração de código
  de indexação vigentes — senão está servindo chunks obsoletos;
- INV-003: página supersedida no bundle está marcada no índice (senão
  vaza para a recuperação padrão);
- PIPE:   todo estágio de pipeline referencia um job existente;
- COG:    estado cognitivo (acessibilidade/agenda) que referencia
  página inexistente é sinalizado (não removido — é dado do usuário).
"""
from __future__ import annotations
from .base import UseCase
from ..okf.authorities import _kb_head
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..settings import Settings

REPAIRABLE = {"INV-001", "INV-002", "INV-003"}   # tudo cai em rebuild_index


class DiagnoseSystem(UseCase):
    def __init__(self, settings: Settings, *, repair: bool = False,
                 known_jobs: set[str] | None = None, notify=None):
        self._settings = settings
        self._repair = repair
        self._known_jobs = known_jobs or set()
        self._notify = notify or (lambda *a, **k: None)

    def execute(self) -> dict:
        findings = (self._check_index_orphans()
                    + self._check_index_freshness()
                    + self._check_superseded()
                    + self._check_pipelines()
                    + self._check_cognitive_orphans())
        repaired = None
        if self._repair and any(f["inv"] in REPAIRABLE for f in findings):
            from ..retrieval.fts import rebuild_index
            # FULL: só o rebuild completo purga órfãos nunca rastreados
            # em page_index_state (o incremental os ignoraria)
            repaired = rebuild_index(self._settings, full=True)
            self._notify("doctor.repaired", {"mode": repaired.get("mode")})
            # reverifica os invariantes reparáveis após o rebuild
            remaining = (self._check_index_orphans()
                         + self._check_index_freshness()
                         + self._check_superseded())
            findings = [f for f in findings if f["inv"] not in REPAIRABLE] \
                + remaining
        return {"ok": not findings, "findings": findings,
                "repaired": repaired,
                "counts": {"error": sum(f["severity"] == "error"
                                        for f in findings),
                           "warn": sum(f["severity"] == "warn"
                                       for f in findings)}}

    # ------------------------------------------------------------- checks
    def _bundle_pages(self) -> set[str]:
        reader = BundleReader(self._settings.path("knowledge") / "bundle")
        return {d.rel_path for d in reader.iter_concepts()}

    def _check_index_orphans(self) -> list[dict]:
        pages = self._bundle_pages()
        idx = connect(self._settings.app_support / "index.db")
        indexed = {r["page"] for r in
                   idx.execute("SELECT DISTINCT page FROM chunks")}
        idx.close()
        orphans = sorted(indexed - pages)
        if not orphans:
            return []
        return [{"inv": "INV-001", "severity": "error",
                 "message": f"{len(orphans)} página(s) no índice sem "
                            f"origem no bundle (rebuild remove)",
                 "sample": orphans[:5], "repairable": True}]

    def _check_index_freshness(self) -> list[dict]:
        from ..retrieval.fts import INDEX_GENERATION
        bundle = self._settings.path("knowledge") / "bundle"
        idx = connect(self._settings.app_support / "index.db")
        meta = {r["key"]: r["value"] for r in
                idx.execute("SELECT key, value FROM index_meta")}
        idx.close()
        out = []
        head = _kb_head(bundle) or ""
        if meta.get("bundle_head") and head and meta["bundle_head"] != head:
            out.append({"inv": "INV-002", "severity": "error",
                        "message": "índice construído sobre outra revisão "
                                   f"({meta['bundle_head'][:8]} ≠ "
                                   f"{head[:8]}) — rebuild",
                        "repairable": True})
        if meta.get("index_generation") not in (None, INDEX_GENERATION):
            out.append({"inv": "INV-002", "severity": "error",
                        "message": f"índice de geração antiga "
                                   f"({meta['index_generation']} ≠ "
                                   f"{INDEX_GENERATION}) — rebuild",
                        "repairable": True})
        return out

    def _check_superseded(self) -> list[dict]:
        reader = BundleReader(self._settings.path("knowledge") / "bundle")
        superseded = {d.rel_path for d in reader.iter_concepts()
                      if d.meta.model_dump(exclude_none=True)
                      .get("superseded_by")}
        if not superseded:
            return []
        idx = connect(self._settings.app_support / "index.db")
        placeholders = ",".join("?" * len(superseded))
        leaking = {r["page"] for r in idx.execute(
            f"SELECT DISTINCT page FROM chunks WHERE page IN "
            f"({placeholders}) AND superseded = 0", tuple(superseded))}
        idx.close()
        if not leaking:
            return []
        return [{"inv": "INV-003", "severity": "error",
                 "message": f"{len(leaking)} página(s) supersedida(s) sem "
                            f"marca no índice (vazam p/ recuperação) — "
                            f"rebuild", "sample": sorted(leaking)[:5],
                 "repairable": True}]

    def _check_pipelines(self) -> list[dict]:
        if not self._known_jobs:
            return []
        import json
        rt = connect(self._settings.app_support / "runtime.db")
        specs = [(r["name"], json.loads(r["spec"])) for r in
                 rt.execute("SELECT name, spec FROM pipelines")]
        rt.close()
        broken = []
        for name, spec in specs:
            missing = [st["job"] for st in spec.get("stages", [])
                       if st["job"] not in self._known_jobs]
            if missing:
                broken.append(f"{name}→{missing}")
        if not broken:
            return []
        return [{"inv": "PIPE", "severity": "warn",
                 "message": "pipeline referencia job inexistente (edite "
                            "ou remova)", "sample": broken[:5],
                 "repairable": False}]

    def _check_cognitive_orphans(self) -> list[dict]:
        pages = self._bundle_pages()
        cog = connect(self._settings.app_support / "cognitive.db")
        items = {r["item"] for r in cog.execute(
            "SELECT DISTINCT item FROM accessibility")}
        cog.close()
        orphans = sorted(items - pages)
        if not orphans:
            return []
        return [{"inv": "COG", "severity": "warn",
                 "message": f"{len(orphans)} item(ns) de acessibilidade "
                            f"referenciam página fora do bundle (histórico "
                            f"preservado — não removido)",
                 "sample": orphans[:5], "repairable": False}]
