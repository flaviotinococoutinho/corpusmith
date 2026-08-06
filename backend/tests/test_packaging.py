"""Recursos empacotados — PR-0.1.

O que estes testes cobrem é o que a CI **não** consegue cobrir barato: o
comportamento do código DENTRO do binário. O job `package` do CI constrói e
sobe o binário de verdade (é ele quem pega `exclude_binaries`, `vec0.so` e o
boot); aqui simula-se `sys.frozen` para exercitar os ramos que só existem lá.

A auditoria (`docs/17`) só verificou que a receita CONSTRUÍA. Rodar o produto
da receita revelou quatro defeitos, dos quais dois vivem no código Python e
portanto pertencem a esta suíte: resolver recurso por `parents[]` e checar
existência de arquivo-fonte que o binário não embarca.
"""
from __future__ import annotations
import ast
from pathlib import Path
import pytest
from llmwiki import paths
from llmwiki.harness import epistemics

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


# ------------------------------------------------------------ paths.resource
def test_frozen_e_falso_na_arvore_de_codigo():
    assert paths.frozen() is False


def test_resource_na_arvore_conta_a_partir_do_source_root(tmp_path):
    assert paths.resource("db", "x.sql", source_root=tmp_path) == (
        tmp_path / "db" / "x.sql")


def test_resource_no_binario_ignora_o_source_root(monkeypatch, tmp_path):
    """`_MEIPASS` manda; `source_root` é irrelevante dentro do binário.

    Medido antes da correção: `FileNotFoundError:
    .../llmwiki-server/db/schema_runtime.sql`, com o arquivo em
    `.../llmwiki-server/_internal/db/schema_runtime.sql`. O daemon morria
    antes de abrir a porta."""
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path / "_internal"),
                        raising=False)
    assert paths.frozen() is True
    assert paths.resource("db", "x.sql", source_root=Path("/qualquer")) == (
        tmp_path / "_internal" / "db" / "x.sql")


# -------------------------------------------------------------- build.spec
def _datas_do_spec() -> list[tuple[str, str]]:
    """Extrai o literal `datas=[...]` do build.spec sem executá-lo (o spec
    importa PyInstaller, que não é dependência da suíte)."""
    arvore = ast.parse((BACKEND / "build.spec").read_text())
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and getattr(no.func, "id", "") == "Analysis":
            for kw in no.keywords:
                if kw.arg == "datas":
                    return [tuple(ast.literal_eval(e)) for e in kw.value.elts]
    raise AssertionError("build.spec sem datas= em Analysis(...)")


def test_datas_declarados_existem():
    """Um `datas` que aponta para arquivo inexistente só falha no dia do
    release — e falha com o binário já publicado se ninguém o rodar."""
    for origem, _destino in _datas_do_spec():
        assert (BACKEND / origem).exists(), f"datas aponta para {origem}"


@pytest.mark.parametrize("recurso", [
    "config/default.yaml",     # settings.py
    "db",                      # runtime/db.py (schema_*.sql)
    "../epistemics.toml",      # harness/epistemics.py — lido em runtime
])
def test_todo_recurso_lido_em_runtime_esta_nos_datas(recurso):
    """Reproduzido no binário: sem o `epistemics.toml` nos `datas`,
    `/cockpit/epistemics` respondia `ok:false, epistemic.registry_missing` e
    o painel Qualidade mostrava "lint com erros" no app instalado."""
    assert recurso in {origem for origem, _ in _datas_do_spec()}


# ---------------------------------------------- lint dentro do binário
def test_lint_no_binario_nao_acusa_refs_ausentes(monkeypatch, tmp_path):
    """A árvore de código não é embarcada: `(_REPO_ROOT/ref).is_file()` diria
    "não existe" para TODOS os `implementation_refs` e o app instalado
    acusaria ~15 erros inexistentes. Em vez de omitir a checagem, o registro
    declara que ela não é respondível ali.

    `_REPO_ROOT` também é simulado: sem isso o teste rodaria contra o
    repositório real, onde os refs existem, e passaria com o ramo `frozen`
    apagado — verde que não prova nada. Medido no binário:
    `_REPO_ROOT` cairia em `backend/dist`, sem `backend/src` embaixo."""
    monkeypatch.setattr(epistemics, "frozen", lambda: True)
    monkeypatch.setattr(epistemics, "_REPO_ROOT", tmp_path)
    resultado = epistemics.lint()
    assert resultado["ok"] is True
    assert not [f for f in resultado["findings"] if f["severity"] == "error"]
    assert "epistemic.refs_uncheckable" in {f["code"]
                                            for f in resultado["findings"]}


def test_na_arvore_o_lint_continua_checando_refs(monkeypatch, tmp_path):
    """O ramo do binário não pode ter afrouxado a checagem no repositório —
    senão a correção de um defeito de empacotamento teria apagado uma regra."""
    assert "epistemic.refs_uncheckable" not in {f["code"] for f in
                                                epistemics.lint()["findings"]}
    mentiroso = tmp_path / "m.toml"
    texto = epistemics.DEFAULT_PATH.read_text()
    alvo = "backend/src/llmwiki/retrieval/streams.py"
    assert alvo in texto, "âncora do teste saiu do registro"
    mentiroso.write_text(texto.replace(
        alvo, "backend/src/llmwiki/nao_existe.py"))
    codigos = {f["code"] for f in epistemics.lint(mentiroso)["findings"]}
    assert "epistemic.implementation_ref_missing" in codigos
