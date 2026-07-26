"""Bloco de relações no corpo — proveniência por REGIÃO (F1-PR4).

O problema que este módulo resolve: `LinkPages` precisa escrever no corpo
canônico, e `UnlinkPages` precisa remover **só o que o ato pôs**. Remover
um link que o humano escreveu na prosa seria reescrever prosa — proibido
(v0.8 §1.2). A resposta é marcar a REGIÃO, não o link: tudo entre as
sentinelas é território do ato; tudo fora é do autor, e o ato não olha.

Decisões que a investigação do PR fixou, cada uma por um defeito MEDIDO:

- **sentinelas ancoradas em linha** (`^...$`, `re.M`) e guarda pela
  CONTAGEM delas, não pela contagem de blocos casados: com um regex
  guloso, um usuário que apaga à mão a sentinela de FECHAMENTO faz o
  bloco casar da primeira abertura até o segundo fechamento — e a
  re-renderização APAGA a prosa que estava no meio. Contar sentinelas
  pega isso; contar matches, não;
- **sentinela dentro de cerca de código é ignorada** (`protected_spans`):
  a primeira vítima seria a página que documenta esta própria feature;
- **texto da entrada nunca puramente numérico**: o bloco fica no fim, e
  `policy.citation_invalid` monta o conjunto `listed` com tudo que vem
  depois de `# Citations`. Uma entrada `- [2024](…)` entraria em `listed`
  e LEGITIMARIA uma citação `[2024]` fabricada na prosa — o ato de
  curadoria desarmando a regra que existe para pegar alucinação;
- **nenhuma regex de link nova**: a gramática da entrada é "linha que
  começa com `- ` e cujo resto é um `MD_LINK` inteiro". Uma terceira
  cópia do padrão seria repetir, no ato de consertá-lo, o erro que este
  PR corrige.
"""
from __future__ import annotations
import re
from .links import MD_LINK, md_link, resolve, safe_link_text
from .regions import RegiaoInconsistente, spans

ABRE = "<!-- llmwiki:relacionados -->"
FECHA = "<!-- /llmwiki:relacionados -->"
TITULO = "## Relacionados"
_ABRE_RE = re.compile(rf"^{re.escape(ABRE)}$", re.M)
_FECHA_RE = re.compile(rf"^{re.escape(FECHA)}$", re.M)
_SO_DIGITOS = re.compile(r"^\d+$")

# A guarda de sentinela vive em `okf/regions.py` desde o F1-PR5, porque o
# `MergePages` precisa da MESMA regra com N regiões em vez de uma. Este
# alias preserva o nome que o ato e os testes do PR4 já usam.
BlocoInconsistente = RegiaoInconsistente


def find_block(body: str) -> tuple[int, int] | None:
    """(início, fim) do bloco, ou None se não houver.

    Recusa qualquer estado que não seja 0 ou 1 par completo: com sentinela
    faltando ou sobrando, re-renderizar engoliria conteúdo do autor."""
    faixas = spans(body, _ABRE_RE, _FECHA_RE,
                   nome="bloco de relações", maximo=1)
    return faixas[0] if faixas else None


def entries_of(body: str) -> dict[str, str]:
    """{rel_path resolvido: linha da entrada} do bloco, na ordem escrita."""
    faixa = find_block(body)
    if faixa is None:
        return {}
    entradas: dict[str, str] = {}
    for linha in body[faixa[0]:faixa[1]].splitlines():
        if not linha.startswith("- "):
            continue
        casou = MD_LINK.fullmatch(linha[2:].strip())
        if casou:
            entradas[casou.group("target")] = linha
    return entradas


def entry_text(title: str, rel_path: str) -> str:
    """Texto da entrada. Puramente numérico viraria entrada de Citations
    (o bloco fica depois dela) e legitimaria citação fabricada."""
    limpo = safe_link_text(title)
    if _SO_DIGITOS.match(limpo):
        limpo = f"{rel_path.rsplit('/', 1)[-1].removesuffix('.md')} {limpo}"
    return limpo


def render_block(entradas: dict[str, str]) -> str:
    corpo = "\n".join(entradas[k] for k in sorted(entradas))
    return f"{ABRE}\n{TITULO}\n\n{corpo}\n{FECHA}"


def _sem_bloco(body: str) -> str:
    faixa = find_block(body)
    if faixa is None:
        return body.rstrip("\n")
    return (body[:faixa[0]] + body[faixa[1]:]).rstrip("\n")


def with_link(body: str, page: str, target: str, title: str,
              rel: str | None = None) -> str:
    """Corpo com a relação page→target garantida no bloco (idempotente).
    Levanta ValueError se a relação já existe — NOOP não vira commit."""
    entradas = entries_of(body)
    alvo = "/" + target
    if any(resolve(t, page) == target for t in entradas):
        raise ValueError(f"relação para {target} já existe no bloco")
    entradas[alvo] = "- " + md_link(entry_text(title, target), target, rel)
    return _sem_bloco(body) + "\n\n" + render_block(entradas) + "\n"


def without_link(body: str, page: str, target: str) -> str:
    """Corpo sem a entrada do bloco que aponta para `target`. Só mexe
    DENTRO das sentinelas — link na prosa é do autor e fica."""
    if find_block(body) is None:
        raise ValueError("esta página não tem bloco de relações — nada que "
                         "este ato tenha escrito para remover")
    entradas = entries_of(body)
    sobra = {t: linha for t, linha in entradas.items()
             if resolve(t, page) != target}
    if len(sobra) == len(entradas):
        raise ValueError(f"o bloco não tem entrada para {target}")
    limpo = _sem_bloco(body)
    if not sobra:
        return limpo + "\n"
    return limpo + "\n\n" + render_block(sobra) + "\n"


def prose_links_to(body: str, page: str, target: str) -> list[str]:
    """Links para `target` que estão FORA do bloco — o ato não os toca, e
    por isso a aresta SOBREVIVE ao unlink. O preview declara isso."""
    faixa = find_block(body)
    fora = []
    for m in MD_LINK.finditer(body):
        if faixa and faixa[0] <= m.start() < faixa[1]:
            continue
        alvo = m.group("target")
        if resolve(alvo, page) == target:
            fora.append(m.group(0))
    return fora
