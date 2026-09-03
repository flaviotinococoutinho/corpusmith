"""Context pack — o mapa DETERMINÍSTICO do repositório para humanos e agentes.

docs/10 §18.4 pedia um `just context` "determinístico (versão, HEAD, camadas,
endpoints, jobs, schemas, flags, invariantes, ADRs ativos, backlog, comandos)
para reduzir alucinação sem enviar o repo inteiro ao contexto". Ficou 🎯 por
dezesseis versões, e o custo foi medido em 2026-09-02: o mesmo fato copiado à
mão em vários documentos, divergindo — mapa de camadas em seis arquivos com
quatro conteúdos, contagens de mecanismos/termos/testes em prosa desatualizada,
selos ✅/🎯 sobre coisas que já existiam ou não.

A regra que este módulo materializa: **o que é enumerável tem dono no código
ou nos registros e é GERADO; à mão fica só o porquê.** Cada seção abaixo lê
a fonte que já é autoridade (architecture.toml, epistemics.toml, ontology.toml,
nfr.toml, SCHEMA_VERSIONS, DERIVATIONS, EVENT_TYPES, os decorators de rota, o
REGISTRY de jobs, os headings de ADR, a cabeça de cada doc) — nunca uma cópia.

Limites ditos: (1) rotas, jobs e use cases são lidos por AST/regex do FONTE,
não por import — este módulo não pode importar `api/` nem `jobs/` sem
violar a regra de dependência que `test_architecture` impõe, e um mapa que
importasse o mundo inteiro para se descrever não seria barato; (2) é
ferramenta de DESENVOLVIMENTO: fora de um checkout do repositório
(binário empacotado) não há fonte a ler e `build()` falha alto em vez de
devolver um mapa vazio fingindo cobertura.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path

from . import __version__
from .harness.epistemics import lint as _epistemics_lint
from .harness.ontology import overview as _ontology_overview
from .kernel.checkpoints import DERIVATIONS
from .runtime.db import SCHEMA_VERSIONS
from .runtime.events import EVENT_TYPES

REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = Path(__file__).resolve().parent

_DOC_HEADER = re.compile(
    r"^> \*\*Altitude:\*\* (?P<alt>[^·]+?) · \*\*Status:\*\* "
    r"(?P<status>vivo|histórico)")
_ADR = re.compile(r"^#{2,4} (ADR-\d+(?:\.\d+)?) — (.+?)\s*$", re.M)
_BACKLOG_ROW = re.compile(r"^\| \*{0,2}(Q-\d+)\*{0,2} \|(.*)$")


class NaoEhUmCheckout(RuntimeError):
    """Sem a árvore de código não há o que mapear — dizer isso é diferente
    de devolver um mapa vazio com cara de completo."""


def _head(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short",
                              "HEAD"], capture_output=True, text=True,
                             timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _routes(root: Path) -> list[str]:
    """`METHOD /caminho` de todo decorator @app.<verbo>("…") em api/*.py —
    a mesma leitura de `test_pontas_soltas`, para que os dois nunca
    divirjam sobre quantas rotas existem."""
    found: list[str] = []
    for py in sorted((root / "backend/src/corpusmith/api").rglob("*.py")):
        for node in ast.walk(ast.parse(py.read_text())):
            if not isinstance(node, ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                verbo = getattr(dec.func, "attr", None)
                if verbo in ("get", "post", "put", "delete", "patch") \
                        and dec.args and isinstance(dec.args[0], ast.Constant):
                    found.append(f"{verbo.upper()} {dec.args[0].value}")
    return sorted(set(found))


def _jobs(root: Path) -> list[str]:
    fonte = (root / "backend/src/corpusmith/jobs/__init__.py").read_text()
    bloco = re.search(r"^REGISTRY = \{(.*?)^\}", fonte, re.S | re.M)
    if not bloco:
        return []
    return sorted(re.findall(r'^\s*"([a-z_]+)":', bloco.group(1), re.M))


def _use_cases(root: Path) -> list[str]:
    found: list[str] = []
    for py in sorted((root / "backend/src/corpusmith/usecases").rglob("*.py")):
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ClassDef) and any(
                    (getattr(b, "id", "") or getattr(b, "attr", ""))
                    .endswith("UseCase") for b in node.bases):
                if not node.name.startswith("_"):
                    found.append(node.name)
    return sorted(set(found))


def _adrs(root: Path) -> list[dict]:
    texto = (root / "docs/08-decisoes.md").read_text()
    return [{"id": i, "title": t} for i, t in _ADR.findall(texto)]


def _docs(root: Path) -> list[dict]:
    out = []
    for md in sorted((root / "docs").glob("*.md")):
        alt, status = "", ""
        for line in md.read_text().splitlines()[:8]:
            m = _DOC_HEADER.match(line)
            if m:
                alt, status = m["alt"].strip(), m["status"]
                break
        out.append({"file": md.name, "altitude": alt, "status": status})
    return out


def _backlog(root: Path) -> dict:
    """A fila corrente de docs/18 §11: linhas `| Q-n | … |`; ✅ na linha
    significa fechada. Sem §11, a fila é vazia — e o mapa diz isso."""
    texto = (root / "docs/18-backlog-consolidado.md").read_text()
    m = re.search(r"^## 11\..*?(?=^## |\Z)", texto, re.S | re.M)
    abertos, fechados = [], []
    if m:
        for line in m.group(0).splitlines():
            row = _BACKLOG_ROW.match(line)
            if row:
                (fechados if "✅" in row.group(2) else abertos).append(
                    row.group(1))
    return {"section": "docs/18 §11", "open": abertos, "closed": fechados}


def _toml(root: Path, nome: str) -> dict:
    return tomllib.loads((root / nome).read_text())


def build(root: Path | str = REPO_ROOT) -> dict:
    """O mapa. Toda lista sai ORDENADA e todo número vem de uma fonte que
    já é autoridade — duas execuções sobre o mesmo HEAD produzem o mesmo
    dicionário (test_context_pack)."""
    root = Path(root)
    if not (root / "architecture.toml").is_file() \
            or not (root / "backend/src/corpusmith").is_dir():
        raise NaoEhUmCheckout(
            f"{root} não é um checkout do Corpusmith (sem architecture.toml "
            "ou sem backend/src) — o context pack lê o FONTE")
    arch = _toml(root, "architecture.toml")
    nfr = _toml(root, "nfr.toml")
    epi = _epistemics_lint(root / "epistemics.toml")
    ont = _ontology_overview(root / "ontology.toml")
    por_status: dict[str, int] = {}
    for n in nfr["nfr"]:
        por_status[n["status"]] = por_status.get(n["status"], 0) + 1
    return {
        "product": {"name": arch["project"]["name"],
                    "version": __version__, "head": _head(root)},
        # `layers` está declarado sob [project] no TOML (a chave vem
        # depois do cabeçalho da tabela) — lê-se de onde ele mora
        "layers": {"order": list(arch["project"]["layers"]),
                   "pure": sorted(arch["pure"]["packages"]),
                   "domain": sorted(arch["domain"]["packages"])},
        "gate": {"ci_enforced": list(arch["gate"]["ci_enforced"]),
                 "verify_enforced": list(arch["gate"]["verify_enforced"]),
                 "commands": dict(sorted(arch["commands"].items()))},
        "invariants": [{"id": i["id"], "rule": i["rule"],
                        "verified_by": list(i["verified_by"])}
                       for i in arch["invariant"]],
        "nfr": {"version": nfr["registry"]["version"],
                "by_status": dict(sorted(por_status.items())),
                "items": [{"id": n["id"], "level": n["level"],
                           "status": n["status"]} for n in nfr["nfr"]]},
        "registries": {
            "epistemics": {"version": epi["registry_version"],
                           "mechanisms": epi["mechanisms"],
                           "lint_ok": epi["ok"],
                           "findings": len(epi["findings"])},
            "ontology": {"version": ont["version"],
                         "axes": len(ont["axes"]),
                         "terms": len(ont["terms"]),
                         "drift_open": sorted(d["name"] for d in ont["drift"]
                                              if d["status"] == "open"),
                         "lint_ok": ont["ok"]}},
        "databases": dict(sorted(SCHEMA_VERSIONS.items())),
        "derivations": dict(DERIVATIONS),
        "events": sorted(EVENT_TYPES),
        "jobs": _jobs(root),
        "endpoints": _routes(root),
        "use_cases": _use_cases(root),
        "adrs": _adrs(root),
        "docs": _docs(root),
        "backlog": _backlog(root),
    }


def render(pack: dict) -> str:
    """Markdown compacto — o que um agente precisa ler ANTES de mudar
    algo, sem o repositório inteiro no contexto."""
    p = pack
    linhas = [
        f"# Corpusmith · context pack — v{p['product']['version']} "
        f"@ {p['product']['head']}",
        "",
        "Gerado por `corpusmith context` (docs/10 §18.4). Fonte de cada "
        "seção: architecture.toml, nfr.toml, epistemics.toml, ontology.toml, "
        "o fonte (rotas/jobs/use cases por AST) e a cabeça de cada doc. "
        "Não edite: regenere.",
        "",
        "## Camadas (gradiente de mutabilidade)",
        "  " + " → ".join(p["layers"]["order"]),
        f"  puras: {', '.join(p['layers']['pure'])}",
        "",
        "## Gate (architecture.toml [gate])",
        f"  CI: {', '.join(p['gate']['ci_enforced'])}",
        f"  just verify: {', '.join(p['gate']['verify_enforced'])}",
        "",
        "## Invariantes",
    ]
    linhas += [f"  {i['id']}: {i['rule']}  ⇐ {', '.join(i['verified_by'])}"
               for i in p["invariants"]]
    nfr = p["nfr"]
    linhas += ["", f"## Requisitos não funcionais (nfr.toml {nfr['version']}) — "
               + ", ".join(f"{k}={v}" for k, v in nfr["by_status"].items())]
    linhas += [f"  {n['id']} [{n['level']}/{n['status']}]" for n in nfr["items"]]
    e, o = p["registries"]["epistemics"], p["registries"]["ontology"]
    linhas += [
        "", "## Registros",
        f"  epistemics.toml {e['version']}: {e['mechanisms']} mecanismos, "
        f"lint {'ok' if e['lint_ok'] else 'COM ERROS'} ({e['findings']} findings)",
        f"  ontology.toml {o['version']}: {o['axes']} eixos, {o['terms']} termos, "
        f"derivas abertas: {', '.join(o['drift_open']) or 'nenhuma'}",
        "", "## Bancos (schema)",
    ]
    linhas += [f"  {k}: v{v}" for k, v in p["databases"].items()]
    linhas += ["", "## Derivações (fonte → derivado)"]
    linhas += [f"  {k} ← {v or 'AUTORIDADE'}" for k, v in p["derivations"].items()]
    linhas += ["", f"## Jobs ({len(p['jobs'])})", "  " + ", ".join(p["jobs"]),
               "", f"## Endpoints ({len(p['endpoints'])})"]
    linhas += [f"  {r}" for r in p["endpoints"]]
    linhas += ["", f"## Use cases ({len(p['use_cases'])})",
               "  " + ", ".join(p["use_cases"]),
               "", f"## Eventos ({len(p['events'])})",
               "  " + ", ".join(p["events"]),
               "", f"## ADRs ({len(p['adrs'])})"]
    linhas += [f"  {a['id']} — {a['title']}" for a in p["adrs"]]
    linhas += ["", "## Documentos (altitude · status)"]
    linhas += [f"  {d['file']}: {d['altitude'] or '?'} · {d['status'] or '?'}"
               for d in p["docs"]]
    b = p["backlog"]
    linhas += ["", f"## Fila corrente ({b['section']}): "
               f"{len(b['open'])} aberto(s), {len(b['closed'])} fechado(s)",
               "  abertos: " + (", ".join(b["open"]) or "nenhum"), ""]
    return "\n".join(linhas)


def to_json(pack: dict) -> str:
    return json.dumps(pack, ensure_ascii=False, indent=1, sort_keys=True)
