"""Testes de ARQUITETURA (v0.9): as regras de projeto não são convenção —
são asserções. Functional core / imperative shell, um método público por
use case, e camadas (adapters → facades → usecases → domain → kernel).
"""
from __future__ import annotations
import ast
import inspect
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "llmwiki"

# o núcleo imutável não pode tocar I/O, rede, processo, framework, schema
FORBIDDEN_IN_PURE = {"sqlite3", "httpx", "subprocess", "fastapi", "uvicorn",
                     "git", "requests", "frontmatter", "yaml", "pydantic",
                     "sse_starlette", "socket", "urllib", "pathlib"}


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


def test_kernel_and_normalize_are_pure():
    """kernel/ e normalize/ são o núcleo IMUTÁVEL: stdlib pura, zero I/O.
    Qualquer import proibido aqui é regressão de arquitetura."""
    for package in ("kernel", "normalize"):
        for module in (SRC / package).rglob("*.py"):
            leaked = _absolute_imports(module) & FORBIDDEN_IN_PURE
            assert not leaked, f"{module}: núcleo puro importou {leaked}"
            outward = _relative_imports(module) - {
                "", "model", "masking", "grammar", "gazetteer", "engine",
                "detectors", "dates", "quantities", "identifiers",
                "standards", "geo", "information", "topology", package}
            assert not outward, \
                f"{module}: núcleo importou camada externa {outward}"


def test_usecases_do_not_reach_outward():
    """usecases importam domain/infra — nunca facades, api, jobs ou
    framework HTTP (Dependency Rule)."""
    for module in (SRC / "usecases").glob("*.py"):
        absolute = _absolute_imports(module)
        relative = _relative_imports(module)
        assert "fastapi" not in absolute, f"{module}: use case importou fastapi"
        assert not relative & {"facades", "api", "jobs"}, \
            f"{module}: use case importou camada mais externa"


def test_api_speaks_only_to_facades():
    """A camada HTTP (mais mutável) orquestra via facades — nunca via
    use cases ou jobs diretamente."""
    for module in (SRC / "api").glob("*.py"):
        relative = _relative_imports(module)
        assert not relative & {"usecases", "jobs"}, \
            f"{module}: api pulou a facade ({relative})"


def test_every_usecase_has_single_public_method():
    """Object Calisthenics: a intenção está no NOME da classe; a única
    porta é execute(). Hooks são protegidos (_underscore)."""
    import llmwiki.usecases.base as base
    import llmwiki.usecases as usecases_pkg
    import importlib
    import pkgutil
    for info in pkgutil.iter_modules(usecases_pkg.__path__):
        module = importlib.import_module(f"llmwiki.usecases.{info.name}")
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
    transport = {"fastapi", "uvicorn", "sse_starlette", "socket",
                 "httpx", "requests", "urllib"}
    for package in ("okf", "harness", "usecases", "facades",
                    "retrieval", "runtime"):
        for module in (SRC / package).rglob("*.py"):
            leaked = _absolute_imports(module) & transport
            assert not leaked, \
                f"{module}: domínio importou transporte {leaked}"


def test_machine_page_template_is_closed_for_modification():
    """Template Method: nenhuma subclasse pode REDEFINIR o esqueleto
    execute() — só preencher hooks (OCP/LSP)."""
    from llmwiki.usecases.base import MachinePageUseCase
    from llmwiki.usecases.compile_source import CompileSource
    from llmwiki.usecases.weekly_review import PublishWeeklyReview
    from llmwiki.usecases.detect_communities import _CommunitySummaryPage
    for subclass in (CompileSource, PublishWeeklyReview,
                     _CommunitySummaryPage):
        assert "execute" not in vars(subclass), \
            f"{subclass.__qualname__} sobrescreveu o esqueleto do template"
        assert subclass.execute is MachinePageUseCase.execute
