"""Blocos do projeto: a fronteira de cada parte do repositório — PURO.

**O que este módulo nomeia.** O repositório tinha registros para o que o
software pode depender (`architecture.toml`), para o que um mecanismo pode
alegar (`epistemics.toml`) e para o que cada palavra significa
(`ontology.toml` §1–§3) — e nenhum para as PARTES do próprio repositório.
Medido em 2026-10-10: oito unidades de código Python (`bench`, `compute`,
`context_pack`, `ingestion`, `jobs_proc`, `paths`, `runtime`, `settings`)
fora da lista de camadas — `compute` estava no mapa do AGENTS §3 e não no
TOML —, três arestas de import apontando para FORA do gradiente e seis em
que `api` pulava a facade, sem que nada as registrasse. Uma regra
estrutural que só vale para os pacotes que ela cita pelo nome deixa de
valer, em silêncio, no primeiro pacote novo.

**O que um bloco do projeto é.** Um conjunto de caminhos do repositório
que responde a UMA pergunta, com o que ele NÃO é declarado ao lado — a
mesma forma de um eixo (§1 do `ontology.toml`). E a mesma propriedade que
define um eixo vale aqui no espaço dos arquivos: assim como nenhum termo
responde a duas perguntas, **nenhum arquivo pertence a dois blocos**.

**Por que "do projeto", qualificado.** "Bloco" já carrega outros sentidos
no código (o bloco sentinelado do corpo, o bloco do grafo, o bloco de
sucessão, o bloco de estudo) — `[drift.block]` no `ontology.toml` os
registra. O sentido novo nasce com qualificador para não engrossar a
deriva que o registro existe para conter.

Tudo aqui opera sobre STRINGS de caminho relativas à raiz do repositório,
com `/` como separador: o núcleo puro não importa `pathlib` (INV-ARCH-001),
e quem lê o disco é a casca (`harness/ontology.py`).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

#: Que TIPO de artefato um bloco agrupa — e portanto que verificação o
#: protege. Vocabulário FECHADO (espelhado em `kernel/ontology.py:
#: VOCABULARIES`, com verbete em `ontology.toml`): tipo novo é decisão,
#: não digitação.
KINDS: tuple[str, ...] = ("code", "test", "registry", "doc", "build")

#: A raiz do pacote Python: o espaço de nomes, não uma unidade do
#: gradiente. Carrega só `__version__` (preso por teste), e por isso a
#: aresta para ela não é acoplamento a declarar.
PACKAGE_ROOT = "backend/src/corpusmith/__init__.py"

#: Onde moram as unidades de código Python — cada pacote ou módulo de
#: topo daqui é UMA unidade do gradiente (`architecture.toml [[tier]]`).
PYTHON_SRC = "backend/src/corpusmith/"


def contem(prefixo: str, caminho: str) -> bool:
    """O caminho declarado `prefixo` cobre `caminho`? Prefixo terminado em
    `/` é diretório (cobre tudo abaixo dele); sem `/` é arquivo exato."""
    if prefixo.endswith("/"):
        return caminho.startswith(prefixo)
    return caminho == prefixo


def bloco_de(caminho: str, blocos: Mapping[str, Iterable[str]]) -> str | None:
    """O bloco que contém o caminho, ou `None` se nenhum contém. Com a
    partição válida (sem sobreposição) há no máximo um; se houver mais de
    um, devolve o primeiro em ordem de nome — e `sobreposicoes()` acusa."""
    donos = sorted(b for b, caminhos in blocos.items()
                   if any(contem(p, caminho) for p in caminhos))
    return donos[0] if donos else None


def sobreposicoes(blocos: Mapping[str, Iterable[str]]
                  ) -> list[tuple[str, str, str, str]]:
    """Pares de caminhos de blocos DIFERENTES em que um cobre o outro —
    um arquivo em dois blocos, a conflação que a partição proíbe.
    Saída ordenada: `(bloco_a, caminho_a, bloco_b, caminho_b)`."""
    planos = sorted((b, p) for b, caminhos in blocos.items()
                    for p in caminhos)
    out: list[tuple[str, str, str, str]] = []
    for i, (ba, pa) in enumerate(planos):
        for bb, pb in planos[i + 1:]:
            if ba != bb and (contem(pa, pb) or contem(pb, pa)):
                out.append((ba, pa, bb, pb))
    return out


def orfaos(arquivos: Iterable[str],
           blocos: Mapping[str, Iterable[str]]) -> list[str]:
    """Arquivos que nenhum bloco cobre — fora do índice, logo fora de
    toda regra que o índice sustenta."""
    return sorted(a for a in arquivos if bloco_de(a, blocos) is None)


def unidade_python(caminho: str) -> str | None:
    """A unidade do gradiente a que um caminho de código Python pertence:
    o pacote (`kernel/…` → `kernel`) ou o módulo de topo (`cli.py` →
    `cli`). A raiz do pacote e caminhos fora de `PYTHON_SRC` → `None`."""
    if not caminho.startswith(PYTHON_SRC) or caminho == PACKAGE_ROOT:
        return None
    resto = caminho[len(PYTHON_SRC):]
    if not resto:
        return None
    if "/" in resto:
        return resto.split("/", 1)[0]
    return resto[:-3] if resto.endswith(".py") else None


def contra_o_gradiente(arestas: Iterable[tuple[str, str]],
                       camada: Mapping[str, int]) -> list[tuple[str, str]]:
    """Arestas `(origem, destino)` em que a origem está numa camada MAIS
    INTERNA que o destino — dependência apontando para fora. Unidade sem
    camada (o que não é código do gradiente) não entra no juízo; quem
    cobra camada para toda unidade é outra regra (`ontology lint`)."""
    return sorted((a, b) for a, b in set(arestas)
                  if a in camada and b in camada and camada[a] < camada[b])


def divergencias(declarado: Iterable[str], real: Iterable[str]
                 ) -> tuple[list[str], list[str]]:
    """(usadas sem declaração, declaradas sem uso). As duas direções
    importam pelo mesmo motivo das derivas do `ontology.toml`: o registro
    não pode apodrecer nem escondendo acoplamento novo, nem cobrando
    acoplamento que já não existe."""
    d, r = set(declarado), set(real)
    return sorted(r - d), sorted(d - r)
