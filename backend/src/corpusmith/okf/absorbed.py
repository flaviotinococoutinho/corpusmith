"""Região de ABSORÇÃO no corpo — o que a fusão escreve (F1-PR5).

`MergePages` funde duas páginas que afirmam a mesma verdade. A pergunta
difícil não é o frontmatter (`kernel/curation.py:merge_meta` já resolve a
união declarada): é o CORPO. Duas respostas erradas e a certa:

- ❌ **reescrever/entrelaçar as duas prosas**: é o eixo de MÁQUINA operando
  sobre texto humano (v0.8 §1.2). Nenhum ato humano reescreve prosa;
- ❌ **não absorver, só suceder**: a perdedora fica legível no caminho dela,
  mas quem lê a vencedora nunca vê aquele texto — "duas versões da mesma
  verdade param de conviver" viraria "uma delas ficou invisível";
- ✅ **absorver INTEGRAL, numa região declarada**: o texto da perdedora
  entra byte a byte entre sentinelas que dizem de onde ele veio. O que o
  ato escreve de próprio é só a linha de cabeçalho com o link para a
  origem — nada da prosa de ninguém é tocado, e um `undo` devolve o
  arquivo idêntico.

Diferença em relação ao bloco de relações (F1-PR4): ali é UM bloco por
página; aqui são N, um por página absorvida, e cada abertura carrega o
caminho da origem. A guarda de sentinela é a mesma e mora em
`okf/regions.py` — escrevê-la de novo repetiria o defeito das duas cópias
do `MD_LINK`.

**Não renumera nota de rodapé.** Se as duas páginas usarem `[1]`, a fusão
deixa as duas ocorrências como estão: renumerar citação é forjar
proveniência. Quando isso faz `policy.citation_invalid` disparar, o preview
mostra o finding e o gate recusa — que é o comportamento certo, não um bug.

**E é por isso que a região NÃO vai no fim do corpo.** `local_policy` monta
o conjunto `listed` com tudo que vem DEPOIS do primeiro `# Citations`, então
uma região no fim cai inteira dentro de `listed` e passa a legitimar
qualquer `[n]` que o texto absorvido cite sem definir. Medido, com o mesmo
corpo e a mesma página: região depois de `# Citations` ⇒ **nenhum finding**;
região antes ⇒ `policy.citation_invalid` (error). Um ato de curadoria
desarmando o detector que existe para pegar citação fabricada é pior do que
não ter o ato. A região entra **antes** da seção de citações quando ela
existe — e a busca da seção copia deliberadamente o regex do detector, sem
"melhorar" o parsing: o que importa é cair do lado certo da fronteira que
ELE usa, não a que um parser ideal usaria.
"""
from __future__ import annotations
import re
from .links import md_link, safe_link_text
from .regions import blocks, spans

_ABRE_FMT = "<!-- corpusmith:absorvido de {} -->"
FECHA = "<!-- /corpusmith:absorvido -->"
_ABRE_RE = re.compile(r"^<!-- corpusmith:absorvido de (?P<origem>[^ ]+) -->$",
                      re.M)
_FECHA_RE = re.compile(rf"^{re.escape(FECHA)}$", re.M)
_NOME = "bloco de absorção"
# MESMO regex do `local_policy.check` — ver docstring do módulo
_CITATIONS_RE = re.compile(r"^#{1,2}\s*Citations\s*$", re.M)


def sources_of(body: str) -> list[str]:
    """Caminhos já absorvidos neste corpo, na ordem em que aparecem."""
    return [m.group("origem")
            for m in blocks(body, _ABRE_RE, _FECHA_RE, nome=_NOME)]


def region_spans(body: str) -> list[tuple[int, int]]:
    return spans(body, _ABRE_RE, _FECHA_RE, nome=_NOME)


def render_region(source: str, title: str, source_body: str) -> str:
    """A região, com o corpo da origem INTACTO entre as sentinelas.

    O título vira texto de link por `safe_link_text` — um `]` no título
    emitiria um NÃO-link (defeito medido no F1-PR4)."""
    cabecalho = "## Incorporado de " + md_link(
        safe_link_text(title) or source, source)
    return (_ABRE_FMT.format(source) + "\n" + cabecalho + "\n\n"
            + source_body.strip("\n") + "\n" + FECHA)


def absorbable(source: str, source_body: str) -> str:
    """O corpo da origem, pronto para entrar na região.

    Duas subtrações, e as duas são de território de ATO, nunca de prosa:

    - **o bloco de relações** (`okf/relations.py`) sai. Se ficasse, suas
      sentinelas entrariam no corpo da vencedora e a próxima chamada de
      `LinkPages`/`UnlinkPages` lá encontraria DOIS pares — `find_block`
      recusaria, e a vencedora ficaria sem poder receber relação nunca
      mais. As relações continuam na página de origem, que segue no bundle
      e é linkada do cabeçalho da região;
    - **regiões de absorção aninhadas** são recusadas, não removidas:
      remover apagaria a prosa que a origem havia absorvido de uma
      TERCEIRA página. Aninhar deixaria as sentinelas em ordem ambígua
      (abre, abre, fecha, fecha), e `regions.blocks` passaria a recusar
      qualquer operação no corpo da vencedora. Limite DECLARADO, com a
      saída legítima na mensagem — a mesma postura do `UndoNotExpressible`.
    """
    from .relations import find_block
    if sources_of(source_body):
        raise ValueError(
            f"{source} já absorveu "
            + ", ".join(sources_of(source_body))
            + " — fundir uma página que já é resultado de fusão aninharia as "
              "regiões e deixaria o corpo ambíguo. Funda no sentido contrário, "
              "ou funda antes as páginas de origem")
    faixa = find_block(source_body)
    if faixa is None:
        return source_body
    return (source_body[:faixa[0]] + source_body[faixa[1]:]).strip("\n")


def with_absorbed(body: str, source: str, title: str,
                  source_body: str) -> str:
    """Corpo da vencedora com a região de `source`.

    Entra ANTES da seção de citações quando ela existe (senão a região cai
    dentro de `listed` e legitima citação fabricada — ver docstring do
    módulo); no fim do corpo quando não existe.

    Recusa absorver duas vezes: a segunda fusão duplicaria o texto e o
    `undo` deixaria de ser byte a byte."""
    if source in sources_of(body):
        raise ValueError(
            f"{source} já foi absorvida nesta página — fundir de novo "
            "duplicaria o texto")
    regiao = render_region(source, title, absorbable(source, source_body))
    citacoes = _CITATIONS_RE.search(body)
    if citacoes:
        antes = body[:citacoes.start()].rstrip("\n")
        return antes + "\n\n" + regiao + "\n\n" + body[citacoes.start():]
    return body.rstrip("\n") + "\n\n" + regiao + "\n"
