"""CurationFacade — a memória sob governo humano: promover, depreciar,
auditar, revisar, refletir."""
from __future__ import annotations
from ..harness.findings import Findings
from ..settings import Settings
from ..usecases.cold_memory import (FreezeMemory, RecycleMemory, cold_stats)
from ..usecases.configure_system import (PRESETS, RollbackConfig,
                                         TuneConfig, config_history,
                                         list_presets)
from ..usecases.export_memory import ExportMemory
from ..usecases.lint_bundle import LintBundle
from ..usecases.manage_tags import RenameTag
from ..usecases.mark_stale import MarkPageStale
from ..usecases.promote_memory import PromoteToMemory
from ..usecases.reflect_usage import ReflectOnUsage, usage_candidates
from ..usecases.weekly_review import ComputeWeeklyReview, PublishWeeklyReview


class CurationFacade:
    def __init__(self, settings: Settings):
        self._settings = settings

    def promote(self, *, kind: str, title: str, content: str,
                source: str = "chat", privacy: str = "local_only",
                description: str | None = None,
                tags: list[str] | None = None,
                resolution: str | None = None,
                target: str | None = None) -> dict:
        return PromoteToMemory(self._settings, kind=kind, title=title,
                               content=content, source=source,
                               privacy=privacy, description=description,
                               tags=tags, resolution=resolution,
                               target=target).execute()

    def mark_stale(self, page_path: str) -> dict:
        return MarkPageStale(self._settings, page_path).execute()

    def lint(self, mode: str = "write") -> Findings:
        return LintBundle(self._settings, mode).execute()

    def weekly_review(self) -> dict:
        """Levantamento puro — sem efeitos (CQS)."""
        return ComputeWeeklyReview(self._settings).execute()

    def publish_review(self, notify=None) -> dict:
        return PublishWeeklyReview(self._settings, notify).execute()

    def reflect(self, notify=None) -> dict:
        return ReflectOnUsage(self._settings, notify).execute()

    def reflect_candidates(self) -> dict:
        return usage_candidates(self._settings)

    # -------------------------------- fila única de próxima ação (R3, v1.8)
    def next_actions(self, *, limit: int = 40) -> dict:
        """A fila "Próxima ação": unifica revisões, lacunas, inbox, pontes
        frágeis e contradições numa só lista ranqueada por VoI/custo."""
        from ..usecases.next_actions import NextActions
        return NextActions(self._settings, limit=limit).execute()

    # ---------------------------------------------- base fria (v0.12)
    def freeze(self, page_path: str, *, force: bool = False,
               reason: str = "") -> dict:
        """T2→T3: congela na base fria (gates ACT-R/TMS validam)."""
        return FreezeMemory(self._settings, page_path, force=force,
                            reason=reason).execute()

    def recycle(self, page_path: str) -> dict:
        """T3→T2: reidrata uma memória fria de volta ao bundle."""
        return RecycleMemory(self._settings, page_path).execute()

    def cold(self) -> dict:
        return cold_stats(self._settings)

    # ------------------------------------------------- Fase 5 (v0.15)
    def rename_tag(self, old: str, new: str | None = None) -> dict:
        """Renomear/fundir (new existente) ou remover (new vazio) uma tag."""
        return RenameTag(self._settings, old, new).execute()

    def export(self, *, format: str = "zip", include_local: bool = False,
               types: list[str] | None = None, tag: str | None = None) -> dict:
        """Export inteligente: local_only fica de fora por default."""
        return ExportMemory(self._settings, format=format,
                            include_local=include_local, types=types,
                            tag=tag).execute()

    # ------------------------------------- configuração versionada (v0.16)
    def tune_config(self, changes: dict, notify=None, *,
                    source: str = "cockpit") -> dict:
        """Ajuste a quente com guard de fitness + linha no ring de 30."""
        return TuneConfig(self._settings, changes, notify,
                          source=source).execute()

    def rollback_config(self, notify=None) -> dict:
        """Retorna à configuração anterior à vigente."""
        return RollbackConfig(self._settings, notify).execute()

    def config_history(self, limit: int = 30) -> list[dict]:
        return config_history(self._settings, limit)

    # ------------------------------------------- presets (UX-4, v1.6.5)
    def preset_list(self) -> list[dict]:
        return list_presets()

    def apply_preset(self, name: str, notify=None) -> dict:
        """Aplica um preset PELA linhagem (source=preset:<nome>) — mesma
        validação, mesmo probe, mesmo rollback dos ajustes manuais."""
        preset = PRESETS[name]                    # KeyError se desconhecido
        return TuneConfig(self._settings, preset["changes"], notify,
                          source=f"preset:{name}",
                          note=preset["description"]).execute()

    # ------------------------------------- referência do mundo (v0.22)
    def reference_stats(self) -> dict:
        from ..usecases.manage_reference import reference_stats
        return reference_stats(self._settings)

    def import_reference(self, payload: dict, notify=None) -> dict:
        from ..usecases.manage_reference import ImportReferenceData
        return ImportReferenceData(self._settings, payload,
                                   notify=notify).execute()

    def seed_reference(self) -> None:
        from ..usecases.manage_reference import seed_reference
        seed_reference(self._settings)

    def check_quotation(self, text: str,
                        claimed_author: str | None = None) -> dict:
        from ..usecases.manage_reference import check_quotation
        return check_quotation(self._settings, text, claimed_author)

    # --------------------------- contratos epistêmicos (v1.6, ADR-38)
    def epistemics_overview(self) -> dict:
        """Lista {id, garantia, status de avaliação, fallback} por
        mecanismo + resultado do lint — a MESMA fonte de CLI e testes."""
        from ..harness.epistemics import lint, load_registry
        from ..usecases.evaluate_memory import envelopes_for
        result = lint()
        mechanisms = []
        if result["registry_version"]:
            registry, _ = load_registry()
            for c in registry.contracts:
                latest = envelopes_for(self._settings, c.mechanism_id,
                                       limit=1)
                mechanisms.append({
                    "mechanism_id": c.mechanism_id,
                    "title": c.title,
                    "decision": c.decision,
                    "guarantee_kind": c.guarantee.kind.value,
                    "guarantee_relative_to": c.guarantee.relative_to,
                    "fallback": [f.value for f in c.fallback],
                    "evaluation_status": (latest[0]["evaluation_status"]
                                          if latest else "unevaluated"),
                    "last_evaluated_at": (latest[0]["created_at"]
                                          if latest else None),
                    "high_impact": c.high_impact})
        return {"lint": result, "mechanisms": mechanisms}

    def epistemics_mechanism(self, mechanism_id: str) -> dict:
        from ..harness.epistemics import load_registry
        from ..usecases.evaluate_memory import envelopes_for
        registry, _ = load_registry()
        contract = registry.get(mechanism_id)
        if contract is None:
            raise KeyError(f"mecanismo desconhecido: {mechanism_id}")
        return {**contract.to_dict(),
                "registry_version": registry.version,
                "evaluations": envelopes_for(self._settings, mechanism_id,
                                             limit=5)}

    def epistemics_evaluations(self, mechanism_id: str,
                               limit: int = 20) -> list[dict]:
        from ..usecases.evaluate_memory import envelopes_for
        return envelopes_for(self._settings, mechanism_id, limit)

    def epistemics_lint(self) -> dict:
        from ..harness.epistemics import lint
        return lint()

    # ------------------------------------ registro ontológico (RFC-004)
    def ontology_overview(self) -> dict:
        """Eixos, termos e deriva semântica + lint — a MESMA fonte de
        CLI, API e testes (nenhuma releitura paralela do TOML)."""
        from ..harness.ontology import overview
        return overview()
