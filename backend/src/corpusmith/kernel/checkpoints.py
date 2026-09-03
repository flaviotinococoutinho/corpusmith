"""Checkpoints: o estado das derivações e as relações entre as fontes — PURO.

**O problema que este módulo normaliza**, e ele é medido nesta árvore: hoje
cada derivação inventa o próprio carimbo de frescor e o próprio invariante.
`bundle_head` aparece em QUATRO lugares — `index_meta` (chave/valor),
`graph_snapshot.bundle_head`, `theme_epochs.bundle_head` e o schema de
runtime — e cada um precisou de um INV separado no doctor: INV-002 para o
índice, INV-004 para o mapa, INV-005 para os temas.

O custo disso não é estético. Foi exatamente essa dispersão que deixou passar
o defeito confirmado por execução nesta sessão: o job `leiden` escrevia
páginas (movendo o HEAD) e o índice ficava para trás, e **nada relacionava as
duas coisas** — o carimbo do mapa dizia estar fresco enquanto o do índice
apodrecia. Cada derivação sabia de si e nenhuma sabia da cadeia.

**A cadeia é o ponto.** As fontes não são independentes: o bundle é a
autoridade, o índice deriva dele, o mapa deriva do índice, os temas derivam
do mapa. Uma derivação pode estar coerente com sua fonte imediata e ainda
assim servir dado velho, porque a fonte da fonte mudou. Declarar essa relação
é o que permite ao doctor dizer QUAL elo quebrou em vez de acender três
alarmes desconexos — e é o que faz a próxima derivação nascer com frescor de
graça, em vez de com mais um carimbo e mais um invariante.

Este módulo é PURO: a topologia e o cálculo de obsolescência. Quem lê estado
real e persiste é `runtime/checkpoints.py`.
"""
from __future__ import annotations
from dataclasses import dataclass

# A CADEIA. `None` como fonte significa AUTORIDADE — o bundle não deriva de
# nada, ele é o que os outros seguem (canônico ≠ projeção).
#
# Acrescentar derivação aqui é o gesto completo: o doctor passa a verificá-la,
# o CLI a listar e a obsolescência transitiva a considerá-la. É deliberado que
# não haja registro dinâmico — uma derivação que o produto não declara é uma
# derivação cujo frescor ninguém garante.
DERIVATIONS: dict[str, str | None] = {
    "bundle": None,          # autoridade: Git + arquivos .md
    "index": "bundle",       # chunks, FTS, entidades, arestas (rebuild_index)
    "graph_map": "index",    # comunidades e pontes (job leiden)
    "centrality": "index",   # intermediação (mesmo job, fonte igual)
    "themes": "graph_map",   # identidade e épocas (RFC-001)
    "stability": "bundle",   # estabilidade editorial (RFC-006 V3) — deriva
                             # DIRETO da autoridade: lê Git + frontmatter,
                             # não o índice, para ser 100% re-derivável
}


class CicloNaCadeia(ValueError):
    """A cadeia de derivações precisa ser um DAG."""


def ancestors(derivation: str) -> list[str]:
    """Cadeia até a autoridade, da fonte imediata para trás.

    É o que torna a obsolescência TRANSITIVA verificável: `themes` estar
    coerente com `graph_map` não basta se `graph_map` está atrás do `index`.
    """
    vistos: list[str] = []
    atual = DERIVATIONS.get(derivation)
    while atual is not None:
        if atual in vistos:
            raise CicloNaCadeia(f"ciclo em {derivation}: {vistos + [atual]}")
        vistos.append(atual)
        if atual not in DERIVATIONS:
            break
        atual = DERIVATIONS[atual]
    return vistos


def descendants(derivation: str) -> list[str]:
    """Tudo que fica obsoleto quando `derivation` muda — em ordem de cadeia."""
    saida: list[str] = []
    fronteira = [derivation]
    while fronteira:
        atual = fronteira.pop(0)
        filhos = sorted(d for d, fonte in DERIVATIONS.items() if fonte == atual)
        for f in filhos:
            if f not in saida:
                saida.append(f)
                fronteira.append(f)
    return saida


@dataclass(frozen=True)
class Checkpoint:
    """Uma derivação, e de qual ESTADO da fonte ela foi produzida."""
    derivation: str
    input_state: str          # estado da fonte na hora (HEAD, ou fingerprint)
    computed_at: float
    detail: str = ""          # JSON livre: contagens, backend, o que servir

    @property
    def source(self) -> str | None:
        return DERIVATIONS.get(self.derivation)


@dataclass(frozen=True)
class Staleness:
    """Veredito sobre uma derivação. `reason` é o que o doctor mostra."""
    derivation: str
    state: str                # 'fresh' | 'stale' | 'stale_upstream' | 'absent'
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.state == "fresh"


def evaluate(checkpoints: dict[str, Checkpoint],
             current: dict[str, str]) -> list[Staleness]:
    """Veredito de cada derivação declarada.

    `current` é o estado ATUAL de cada fonte (para o bundle, o HEAD; para as
    demais, o `input_state` que elas registraram — a saída de uma é a entrada
    da seguinte).

    Três vereditos distintos, e a distinção é o ganho sobre carimbos soltos:

    - `absent`  — nunca computada. **Não é defeito**: instalação nova não tem
      mapa velho, tem mapa nenhum, e acusar isso viraria ruído em todo doctor
      recém-instalado (a mesma razão do INV-004);
    - `stale`   — a fonte IMEDIATA mudou desde o cálculo;
    - `stale_upstream` — a derivação está coerente com a fonte imediata, mas
      um ancestral mudou. É o caso que carimbo isolado NÃO pega, e é o que
      deixou o INV-002 passar: o mapa dizia-se fresco com o índice atrás.
    """
    vereditos: dict[str, Staleness] = {}
    for derivation in DERIVATIONS:
        fonte = DERIVATIONS[derivation]
        if fonte is None:
            vereditos[derivation] = Staleness(derivation, "fresh")
            continue
        cp = checkpoints.get(derivation)
        if cp is None:
            vereditos[derivation] = Staleness(derivation, "absent",
                                              "nunca computada")
            continue
        esperado = current.get(fonte)
        if esperado is not None and cp.input_state != esperado:
            vereditos[derivation] = Staleness(
                derivation, "stale",
                f"computada de {fonte}={_curto(cp.input_state)}, "
                f"{fonte} está em {_curto(esperado)}")
            continue
        vereditos[derivation] = Staleness(derivation, "fresh")

    # segunda passada: obsolescência TRANSITIVA. Ordem por profundidade para o
    # veredito do ancestral já estar decidido quando o filho é avaliado.
    for derivation in sorted(DERIVATIONS, key=lambda d: len(ancestors(d))):
        v = vereditos[derivation]
        if v.state != "fresh":
            continue
        for anc in ancestors(derivation):
            va = vereditos.get(anc)
            if va and va.state in ("stale", "stale_upstream"):
                vereditos[derivation] = Staleness(
                    derivation, "stale_upstream",
                    f"coerente com {DERIVATIONS[derivation]}, mas "
                    f"{anc} está desatualizada")
                break
    return [vereditos[d] for d in DERIVATIONS]


def _curto(estado: str) -> str:
    return estado[:8] if len(estado) > 8 else (estado or "vazio")
