"""Testes de ARQUITETURA (v0.9): as regras de projeto não são convenção —
são asserções. Functional core / imperative shell, um método público por
use case, e camadas (adapters → facades → usecases → domain → kernel).
"""
from __future__ import annotations
import ast
import inspect
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "corpusmith"

# o núcleo imutável não pode tocar I/O, rede, processo, framework, schema
FORBIDDEN_IN_PURE = {"sqlite3", "httpx", "subprocess", "fastapi", "uvicorn",
                     "git", "requests", "frontmatter", "yaml", "pydantic",
                     "sse_starlette", "socket", "urllib", "pathlib"}
# transporte proibido nos domínios (falar com o mundo é só dos adapters)
TRANSPORT = {"fastapi", "uvicorn", "sse_starlette", "socket",
             "httpx", "requests", "urllib"}
PURE_PACKAGES = ("kernel", "normalize", "cognitive", "epistemic")
DOMAIN_PACKAGES = ("okf", "harness", "usecases", "facades",
                   "retrieval", "runtime", "cognitive", "epistemic",
                   "compute")


def _absolute_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            found.add((node.module or "").split(".")[0])
    return found


def _relative_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            found.add((node.module or "").split(".")[0])
    return found


def _internal_imports(path: Path) -> set[str]:
    """Pacotes de corpusmith alcançados por QUALQUER forma de import —
    relativo (`from ..facades import X`) ou absoluto
    (`from corpusmith.facades import X` / `import corpusmith.facades`).

    T7 (docs/18 §5.2): INV-ARCH-003/004 só olhavam os relativos, então
    reescrever a violação em forma absoluta passava verde — o cético
    plantou exatamente isso."""
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            parts = (node.module or "").split(".")
            if node.level > 0:
                found.add(parts[0])
            elif parts[0] == "corpusmith" and len(parts) > 1:
                found.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "corpusmith" and len(parts) > 1:
                    found.add(parts[1])
    return found


def test_kernel_and_normalize_are_pure():
    """kernel/, normalize/, cognitive/ e epistemic/ são núcleo PURO:
    stdlib, zero I/O, zero framework. O domínio cognitivo (v0.19) e o
    epistêmico (v1.6) são testáveis sem SQLite/FastAPI/LLM/filesystem
    por construção."""
    own_modules = {
        "", "model", "masking", "grammar", "gazetteer", "engine",
        "detectors", "dates", "quantities", "identifiers",
        "standards", "geo", "information", "topology",
        "policy", "gates", "scoring", "projection", "practice", "session",
        "parse", "validate",
        "ontology",   # RFC-004: curation.py delega a regra de eixos
        "vitality"}   # RFC-006 V3: stability.py LÊ `aposentada` de lá —
                      # o sentido de ciclo tem UM dono, não dois
    for package in PURE_PACKAGES:
        for module in (SRC / package).rglob("*.py"):
            leaked = _absolute_imports(module) & FORBIDDEN_IN_PURE
            assert not leaked, f"{module}: núcleo puro importou {leaked}"
            outward = _relative_imports(module) - own_modules - {package}
            assert not outward, \
                f"{module}: núcleo importou camada externa {outward}"


def test_memory_domain_does_not_depend_on_cognitive_domain():
    """v0.19: a dependência é UNIDIRECIONAL — o plano cognitivo lê a
    memória (via views montadas nos adapters); a memória JAMAIS conhece
    o plano cognitivo. kernel/normalize/okf/harness/retrieval/epistemic
    limpos."""
    for package in ("kernel", "normalize", "okf", "harness", "retrieval",
                    "epistemic"):
        for module in (SRC / package).rglob("*.py"):
            relative = _relative_imports(module)
            assert "cognitive" not in relative, \
                f"{module}: domínio de memória importou cognitive/"


def test_usecases_do_not_reach_outward():
    """usecases importam domain/infra — nunca facades, api, jobs ou
    framework HTTP (Dependency Rule)."""
    # rglob, não glob (F1-PR1): `usecases/curate/` é um SUBPACOTE e
    # escaparia em silêncio de INV-ARCH-003 se a varredura fosse plana
    for module in (SRC / "usecases").rglob("*.py"):
        absolute = _absolute_imports(module)
        assert "fastapi" not in absolute, f"{module}: use case importou fastapi"
        # T7: _internal_imports vê relativo E absoluto — reescrever
        # `from ..facades` como `from corpusmith.facades` não escapa mais
        assert not _internal_imports(module) & {"facades", "api", "jobs"}, \
            f"{module}: use case importou camada mais externa"


def test_api_speaks_only_to_facades():
    """A camada HTTP (mais mutável) orquestra via facades — nunca via
    use cases ou jobs diretamente."""
    # rglob + _internal_imports (T7): subpacote novo de api/ e import
    # absoluto entram no invariante no dia em que nascerem
    for module in (SRC / "api").rglob("*.py"):
        internal = _internal_imports(module)
        assert not internal & {"usecases", "jobs"}, \
            f"{module}: api pulou a facade ({internal})"


def test_every_usecase_has_single_public_method():
    """Object Calisthenics: a intenção está no NOME da classe; a única
    porta é execute(). Hooks são protegidos (_underscore)."""
    import corpusmith.usecases.base as base
    import corpusmith.usecases as usecases_pkg
    import importlib
    import pkgutil
    # walk_packages, não iter_modules (F1-PR1): iter_modules NÃO desce em
    # subpacotes, então um ato em `usecases/curate/supersede.py` ficaria
    # fora de INV-ARCH-005 — exatamente a camada que este PR inaugura
    for info in pkgutil.walk_packages(usecases_pkg.__path__,
                                      prefix="corpusmith.usecases."):
        module = importlib.import_module(info.name)
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if not issubclass(cls, base.UseCase) or cls is base.UseCase:
                continue
            if cls.__module__ != module.__name__:
                continue
            public = [n for n, member in vars(cls).items()
                      if callable(member) and not n.startswith("_")]
            assert public in ([], ["execute"]), \
                f"{cls.__qualname__}: métodos públicos além de execute: {public}"


def test_domain_is_free_of_framework_and_transport():
    """v0.16: os DOMÍNIOS (okf, harness, usecases, facades, retrieval) e o
    runtime não conhecem framework HTTP nem transporte — falar com o mundo
    é privilégio de api/, cli, daemon e models/ (o adapter de LLM). Assim a
    regra 'domínio não depende de framework, I/O de rede ou transporte'
    é asserção executável, não convenção."""
    for package in DOMAIN_PACKAGES:
        for module in (SRC / package).rglob("*.py"):
            leaked = _absolute_imports(module) & TRANSPORT
            assert not leaked, \
                f"{module}: domínio importou transporte {leaked}"


def test_machine_page_template_is_closed_for_modification():
    """Template Method: nenhuma subclasse pode REDEFINIR o esqueleto
    execute() — só preencher hooks (OCP/LSP)."""
    from corpusmith.usecases.base import MachinePageUseCase
    from corpusmith.usecases.compile_source import CompileSource
    from corpusmith.usecases.weekly_review import PublishWeeklyReview
    from corpusmith.usecases.detect_communities import _CommunitySummaryPage
    for subclass in (CompileSource, PublishWeeklyReview,
                     _CommunitySummaryPage):
        assert "execute" not in vars(subclass), \
            f"{subclass.__qualname__} sobrescreveu o esqueleto do template"
        assert subclass.execute is MachinePageUseCase.execute
