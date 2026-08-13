"""Configuração central (Parte V §5.1 + with_overrides v0.6 §5.2 +
resolve_privacy Manual Ap. D).

Precedência: overrides explícitos > $CORPUSMITH_CONFIG > config/default.yaml
empacotado > defaults de código. Privacidade default é `local_only`:
nada sai da máquina sem regra explícita liberando.
"""
from __future__ import annotations
import copy
import fnmatch
import os
from pathlib import Path
from typing import Any, ClassVar
import yaml
from pydantic import BaseModel, ConfigDict

from .paths import resource as _resource
_DEFAULT_CONFIG = _resource(
    "config", "default.yaml",
    source_root=Path(__file__).resolve().parents[2])


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Settings(BaseModel):
    model_config = ConfigDict(extra="allow")

    home: Path = Path("~/corpusmith")
    paths: dict[str, str] = {
        "knowledge": "knowledge",
        "adapters": "adapters",
        "models": "models",
        "logs": "logs",
    }
    server: dict[str, Any] = {"host": "127.0.0.1", "port": 8377}
    privacy: dict[str, Any] = {"default": "local_only", "rules": []}
    budget: dict[str, Any] = {"daily_usd": 2.0}
    policy: dict[str, Any] = {"citation_required": True}
    # `chat` é uma ESCADA de preferência (ADR-42): o roteador escolhe a
    # primeira entrada instalada que caiba em `memory_fraction` da RAM.
    # Aceita string também, para config anterior a v1.9.
    models: dict[str, Any] = {
        "local": {"provider": "ollama", "base_url": "http://127.0.0.1:11434",
                  "chat": ["qwen3-vl:8b-instruct", "qwen3-vl:4b-instruct",
                           "qwen3-vl:4b", "qwen3-vl:2b-instruct",
                           "qwen2.5:7b-instruct"],
                  "embed": "nomic-embed-text", "memory_fraction": 0.6},
        "api": {"provider": "anthropic", "chat": "claude-haiku-4-5-20251001"},
    }
    worker: dict[str, Any] = {"heavy_slots": 1, "light_slots": 2,
                              "poll_seconds": 1.0}
    flags: dict[str, bool] = {"retrieval.descend": True,
                              "reconcile.llm_arbiter": False}
    ask: dict[str, Any] = {"abstain_threshold": 0.0}
    # política da base fria (v0.12): critério ACT-R de esquecimento
    memory: dict[str, Any] = {"freeze_tau": 0.0,          # limiar τ
                              "activation_noise": 0.4,    # ruído s
                              "max_recall_probability": 0.05,
                              "min_idle_days": 90,
                              "auto_recycle": False}
    # variações do método de captura/organização (Fase 5, editável no app);
    # pairwise_max: acima disso a clusterização troca pares O(n²) por
    # índice invertido + bandas LSH (seleção adaptativa, v0.16)
    consolidate: dict[str, Any] = {"min_shared": 2, "min_cluster": 2,
                                   "pairwise_max": 32}
    # camada cognitiva (v0.18): perfil DECLARADO (vence o observado —
    # preferred_strategy != "auto" desliga a seleção Hedge) e parâmetros
    # do convívio (TTL do estado, suporte mínimo p/ observação, corte de
    # carga alta que reduz a entrega)
    profile: dict[str, Any] = {"preferred_strategy": "auto",
                               "formalism": "medio",
                               "analogies": True}
    cognitive: dict[str, Any] = {"state_ttl_hours": 8,
                                 "high_load": 4,
                                 "min_support": 5}

    # seções que o Cockpit pode editar a quente (POST /cockpit/config)
    TUNABLE_SECTIONS: ClassVar[tuple[str, ...]] = (
        "flags", "ask", "memory", "policy", "consolidate",
        "profile", "cognitive")

    # ------------------------------------------------------------------ paths
    @property
    def app_support(self) -> Path:
        p = self.home.expanduser() / "state"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def path(self, name: str) -> Path:
        p = self.home.expanduser() / self.paths.get(name, name)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ---------------------------------------------------------------- privacy
    def resolve_privacy(self, rel_path: str) -> str:
        """Privacidade EFETIVA de uma fonte (glob rules → default).
        A primeira regra que casar vence; sem regra → default (local_only)."""
        for rule in self.privacy.get("rules", []):
            if fnmatch.fnmatch(rel_path, rule.get("pattern", "")):
                return rule.get("privacy", self.privacy.get("default", "local_only"))
        return self.privacy.get("default", "local_only")

    # ------------------------------------------------------------ flags/get
    def flag(self, name: str, default: bool = False) -> bool:
        return bool(self.flags.get(name, default))

    def get(self, dotted: str, default: Any = None) -> Any:
        """Lookup 'secao.chave' sobre o modelo (ex.: 'ask.abstain_threshold')."""
        cur: Any = self.model_dump(mode="python")
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    # -------------------------------------------------------------- overrides
    def with_overrides(self, **overrides: Any) -> "Settings":
        merged = _deep_merge(self.model_dump(mode="python"), overrides)
        return Settings(**merged)

    # ------------------------------------------------- overrides persistidos
    def tune(self, changes: dict[str, dict]) -> dict:
        """Aplica ajustes A QUENTE (mutação das seções compartilhadas —
        todos os use cases leem via get()/flag() no momento do execute)
        e PERSISTE em overrides.yaml para sobreviver ao restart.
        Só seções em TUNABLE_SECTIONS; chaves desconhecidas rejeitam."""
        for section, values in changes.items():
            if section not in self.TUNABLE_SECTIONS:
                raise ValueError(f"seção não ajustável: {section}")
            if not isinstance(values, dict):
                raise ValueError(f"{section}: esperado objeto")
            getattr(self, section).update(values)
        overrides_path = self.app_support / "overrides.yaml"
        stored = {}
        if overrides_path.is_file():
            stored = yaml.safe_load(overrides_path.read_text()) or {}
        merged = _deep_merge(stored, changes)
        overrides_path.write_text(yaml.safe_dump(merged, sort_keys=True))
        return self.snapshot()

    def snapshot(self) -> dict:
        return {section: dict(getattr(self, section))
                for section in self.TUNABLE_SECTIONS}

    # ------------------------------------------------------------------- load
    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Settings":
        data: dict = {}
        # LLMWIKI_* aceito como fallback (ADR-52): instalação existente com o
        # env var antigo continua encontrando o próprio HOME — renomear o
        # produto não pode desligar a memória de ninguém em silêncio.
        candidate = (config_path or os.environ.get("CORPUSMITH_CONFIG")
                     or os.environ.get("LLMWIKI_CONFIG") or _DEFAULT_CONFIG)
        candidate = Path(candidate).expanduser()
        if candidate.is_file():
            data = yaml.safe_load(candidate.read_text()) or {}
        if home := (os.environ.get("CORPUSMITH_HOME")
                    or os.environ.get("LLMWIKI_HOME")):
            data["home"] = home
        elif "home" not in data and not Path("~/corpusmith").expanduser() \
                .exists() and Path("~/llmwiki").expanduser().exists():
            # instalação anterior ao rename, sem env var nem config: o HOME
            # antigo com dados VENCE um HOME novo vazio — o corpus do usuário
            # não pode sumir porque o produto mudou de nome
            data["home"] = "~/llmwiki"
        settings = cls(**data)
        overrides = settings.app_support / "overrides.yaml"
        if overrides.is_file():                # ajustes feitos pelo Cockpit
            stored = yaml.safe_load(overrides.read_text()) or {}
            settings = settings.with_overrides(**{
                k: v for k, v in stored.items()
                if k in cls.TUNABLE_SECTIONS})
        return settings
