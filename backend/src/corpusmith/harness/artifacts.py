"""Gate dos ARTEFATOS do bundle — arquivos que não são página OKF (Q-28).

A conformidade OKF e a política local olham PÁGINAS (frontmatter, links,
privacidade, sucessão). O bundle carrega também um arquivo que não é
página: o golden eval (`harness/golden_eval.jsonl`), o INSTRUMENTO contra
o qual os mecanismos são medidos (`usecases/evaluate_memory.py`). Até o
ADR-61 ele entrava por `write_text` fora do escritor e sem validação — um
golden malformado só explodia na hora do eval (`KeyError` em
`case["q"]`), depois de já estar no histórico. Instrumento que aceita
qualquer coisa faz toda medição feita com ele herdar o defeito.

Duas regras, com código estável (mesma família `policy.*` da política
local, e pelo mesmo `HarnessRejection`):

- `policy.artifact_unknown` — caminho fora da allowlist FECHADA abaixo:
  sem ela, `BundleWriter.write_artifact` viraria a porta lateral genérica
  que existe para fechar (página entra por `write`, com o Harness inteiro);
- `policy.artifact_invalid` — conteúdo fora do formato do artefato.
"""
from __future__ import annotations

import json
import re

from .findings import Finding, Findings

GOLDEN_EVAL = "harness/golden_eval.jsonl"

#: Chaves opcionais de um caso do golden e o tipo que o eval espera delas
#: (`EvaluateMemory._grade`, `_rank_metrics`, `as_of` do `AskMemory`).
_OPCIONAIS: dict[str, type] = {"as_of": str, "expect_abstain": bool,
                               "expect_pages": list, "expect_regex": str}


def _golden(texto: str) -> list[str]:
    linhas = [(n, l) for n, l in enumerate(texto.splitlines(), 1)
              if l.strip()]
    if not linhas:
        return ["golden sem nenhum caso — instrumento vazio não mede nada"]
    erros: list[str] = []
    for n, linha in linhas:
        try:
            caso = json.loads(linha)
        except json.JSONDecodeError as e:
            erros.append(f"linha {n}: JSON inválido ({e.msg})")
            continue
        if not isinstance(caso, dict):
            erros.append(f"linha {n}: o caso precisa ser um objeto JSON")
            continue
        for chave in ("q", "category"):
            valor = caso.get(chave)
            if not isinstance(valor, str) or not valor.strip():
                erros.append(f"linha {n}: `{chave}` ausente ou vazio — o "
                             f"eval lê `case[{chave!r}]` e quebraria")
        for chave, tipo in _OPCIONAIS.items():
            if chave in caso and not isinstance(caso[chave], tipo):
                erros.append(f"linha {n}: `{chave}` deveria ser "
                             f"{tipo.__name__}")
        paginas = caso.get("expect_pages")
        if isinstance(paginas, list) and not all(
                isinstance(p, str) and p for p in paginas):
            erros.append(f"linha {n}: `expect_pages` deve listar caminhos")
        padrao = caso.get("expect_regex")
        if isinstance(padrao, str):
            try:
                re.compile(padrao)
            except re.error as e:
                erros.append(f"linha {n}: `expect_regex` não compila ({e})")
    return erros


#: Allowlist FECHADA: caminho relativo ao bundle → validador do formato.
#: Artefato novo é decisão (ADR), não caminho livre.
ARTIFACTS = {GOLDEN_EVAL: _golden}


def check(rel_path: str, texto: str) -> Findings:
    """Findings do gate de artefato — vazio quando pode entrar."""
    validar = ARTIFACTS.get(rel_path)
    if validar is None:
        return Findings([Finding(
            "error", "policy.artifact_unknown", rel_path,
            f"`{rel_path}` não é artefato declarado do bundle (allowlist: "
            f"{sorted(ARTIFACTS)}) — página entra por `write`, e artefato "
            "novo é decisão, não caminho livre")])
    return Findings(Finding("error", "policy.artifact_invalid", rel_path, erro)
                    for erro in validar(texto))
