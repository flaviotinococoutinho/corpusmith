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
- INV-004: o mapa de padrões (comunidades/pontes) corresponde ao HEAD do
  bundle, e nenhuma ponte aponta para página aposentada (F2-PR1);
- PIPE:   todo estágio de pipeline referencia um job existente;
- COG:    estado cognitivo (acessibilidade/agenda) que referencia
  página inexistente é sinalizado (não removido — é dado do usuário).
"""
from __future__ import annotations
from pathlib import Path
from .base import UseCase
from ..okf.authorities import _kb_head
from ..okf.bundle import BundleReader
from ..runtime.db import connect
from ..settings import Settings


class _SmokeConn:
    """Grafo mínimo em memória para o smoke da camada nativa (doctor)."""

    def execute(self, sql, *args):
        if "graph_edges" in sql:
            return [("a", "b", "extracted"), ("b", "c", "inferred")]

        class _R:
            @staticmethod
            def fetchall():
                return []
        return _R()

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
                    + self._check_cognitive_orphans()
                    + self._check_graph_snapshot())
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
                "native": self._check_native(),
                "graph": self._graph_report(),
                "counts": {"error": sum(f["severity"] == "error"
                                        for f in findings),
                           "warn": sum(f["severity"] == "warn"
                                       for f in findings)}}

    def _check_native(self) -> dict:
        """ADR-39 §22: estado da camada nativa — INFORMATIVO (a ausência
        NÃO é erro: o fallback Python é comportamento suportado; vira
        problema só se compute.backend=rust sem allow_fallback)."""
        from ..compute import get_kernel, selection_report
        from ..compute.graph_cache import graph_cache_stats
        report: dict = {"fallback_available": True}
        try:
            kernel = get_kernel(self._settings, refresh=True)
            info = kernel.backend_info()
            report["effective_backend"] = info.name
            report["selection"] = selection_report()
            if info.name == "rust":
                # smoke: PPR mínimo prova extensão + protocolo + GIL
                graph = kernel.load_graph(
                    index_path="", connection=_SmokeConn())
                ranked = kernel.personalized_pagerank(
                    graph, {"a": 1.0}, top_k=2)
                report["smoke_ppr_ok"] = bool(ranked)
                report["native_version"] = info.version
                report["native_build"] = info.build
        except Exception as e:                       # noqa: BLE001
            report["effective_backend"] = "python"
            report["error"] = f"{type(e).__name__}: {e}"
        worker = Path(__file__).resolve().parents[4] / "native" \
            / "target" / "release" / "llmwiki-native-worker"
        report["native_worker_present"] = worker.is_file()
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(
                    dir=self._settings.app_support, delete=True):
                report["tmp_dir_writable"] = True
        except OSError:
            report["tmp_dir_writable"] = False
        report["graph_cache"] = graph_cache_stats()
        return report

    def _graph_report(self) -> dict:
        """Estado do mapa de padrões — INFORMATIVO, ao lado do `native`.

        `backend` é o campo que decide se o usuário confia no mapa: numa
        máquina em que o extra `[ml]` não compilou, o produto cai no
        fallback de componentes conexos e chama o resultado de
        "comunidade". Antes do carimbo (F2-PR1) isso era invisível."""
        idx = connect(self._settings.app_support / "index.db")
        try:
            row = idx.execute("SELECT * FROM graph_snapshot WHERE id=1"
                              ).fetchone()
        except Exception:
            return {"computed": False}
        finally:
            idx.close()
        if row is None:
            return {"computed": False}
        return {"computed": True, **{k: row[k] for k in row.keys()
                                     if k != "id"}}

    def _check_graph_snapshot(self) -> list[dict]:
        """INV-004: mapa de padrões coerente com o canônico.

        Duas divergências, as duas WARN e não ERROR — mapa velho não é
        corrupção, é mapa velho, e o produto tem de poder SERVI-LO com
        aviso em vez de recomputar. Essa distinção é o que torna o mapa
        usável numa máquina pequena, onde recomputar do zero a cada
        abertura não é opção.

        Mapa AUSENTE não é finding: instalação nova não tem mapa velho,
        tem mapa nenhum, e acusar isso viraria ruído em todo `doctor`
        recém-instalado."""
        estado = self._graph_report()
        if not estado.get("computed"):
            return []
        out: list[dict] = []
        # `_kb_head` resolve `.git` a partir do PAI do caminho dado —
        # o mesmo argumento que o INV-002 usa (`kb/bundle`)
        head = _kb_head(self._settings.path("knowledge") / "bundle")
        if estado.get("bundle_head") and head \
                and estado["bundle_head"] != head:
            out.append({
                "inv": "INV-004", "severity": "warn",
                "detail": f"mapa de padrões computado em "
                          f"{estado['bundle_head'][:8]}, HEAD em "
                          f"{head[:8]} — comunidades e pontes podem não "
                          f"refletir o bundle atual (rode o job `leiden`)"})
        idx = connect(self._settings.app_support / "index.db")
        try:
            orfas = idx.execute(
                "SELECT COUNT(*) c FROM graph_bridges WHERE src IN "
                "(SELECT DISTINCT page FROM chunks WHERE superseded=1) "
                "OR dst IN "
                "(SELECT DISTINCT page FROM chunks WHERE superseded=1)"
            ).fetchone()["c"]
        except Exception:
            orfas = 0
        finally:
            idx.close()
        if orfas:
            out.append({
                "inv": "INV-004", "severity": "warn",
                "detail": f"{orfas} ponte(s) frágil(is) apontando para "
                          "página aposentada — a fila ofereceria reforçar "
                          "um fio para lugar nenhum"})
        return out

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
