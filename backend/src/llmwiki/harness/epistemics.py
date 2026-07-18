"""Loader do registro epistêmico (shell) — a ÚNICA implementação de
carga/validação, compartilhada por CLI, facade, API e testes (ADR-38).

Lê epistemics.toml (raiz do repo, override por caminho explícito), delega
parsing e regras ao domínio PURO (epistemic/) e acrescenta a única
checagem que exige filesystem: existência dos implementation_refs.
Somente leitura — o loader jamais escreve (propriedade testada).
"""
from __future__ import annotations
from pathlib import Path
from ..epistemic import (Finding, Registry, RegistryError, parse_registry,
                         validate_registry)

# harness/ → llmwiki → src → backend → raiz do repo
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATH = _REPO_ROOT / "epistemics.toml"


def load_registry(path: Path | str | None = None
                  ) -> tuple[Registry, tuple[Finding, ...]]:
    """Registro + findings (parsing ∪ regras ∪ refs inexistentes),
    ordenados deterministicamente. RegistryError se inparseável ou de
    versão incompatível; FileNotFoundError se o arquivo não existir."""
    toml_path = Path(path) if path else DEFAULT_PATH
    registry, parse_findings = parse_registry(toml_path.read_text())
    referenced = {ref for contract in registry.contracts
                  for ref in contract.implementation_refs}
    existing = frozenset(ref for ref in referenced
                         if (_REPO_ROOT / ref).is_file())
    rule_findings = validate_registry(registry, existing_refs=existing)
    merged = sorted(set(parse_findings) | set(rule_findings),
                    key=lambda f: (f.mechanism_id, f.code, f.message))
    return registry, tuple(merged)


def lint(path: Path | str | None = None) -> dict:
    """Resultado estruturado para CLI/API/painel — a MESMA fonte."""
    try:
        registry, findings = load_registry(path)
    except FileNotFoundError:
        return {"ok": False, "registry_version": None, "mechanisms": 0,
                "findings": [{"code": "epistemic.registry_missing",
                              "severity": "error", "mechanism_id": "",
                              "message": "epistemics.toml não encontrado"}]}
    except RegistryError as e:
        return {"ok": False, "registry_version": None, "mechanisms": 0,
                "findings": [{"code": "epistemic.registry_unreadable",
                              "severity": "error", "mechanism_id": "",
                              "message": str(e)}]}
    errors = sum(1 for f in findings if f.severity == "error")
    return {"ok": errors == 0,
            "registry_version": registry.version,
            "mechanisms": len(registry.contracts),
            "findings": [f.to_dict() for f in findings]}
