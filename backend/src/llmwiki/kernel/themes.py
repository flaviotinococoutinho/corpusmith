"""Casamento de partições e identidade de tema — núcleo PURO (RFC-001).

Aqui mora a decisão que o `docs/16` (RFC-001) autoriza: dada a partição da
época anterior e a nova, **qual tema é o mesmo tema** e **que evento
aconteceu**. Nenhuma I/O, nenhum banco, nenhum modelo — é o que torna a
decisão testável sem montar bundle, e é a razão de `theme_id` não poder
depender do LLM.

**A calibração está no RFC e vale repetir a parte que muda o desenho.** Sete
perturbações medidas com os caminhos das páginas preservados:

| perturbação | Jaccard | forma |
|---|---:|---|
| 1 página nova (6→7) | 0,86 | 1↔1 |
| +50 % / −33 % | 0,67 | 1↔1 |
| **tema dobra (6→12)** | **0,50** | 1↔1 |
| **tema parte em dois trios** | **0,50** | **1→2** |
| tema dissolve | 0,17 | 1→0 |

Duas consequências:

1. **τ = 0,5 é o pior valor possível** — é exatamente o Jaccard de um
   crescimento legítimo E de um split. `TAU = 1/3` é o ponto médio da banda
   vazia medida entre 0,17 e 0,50, a única região em que o limiar não decide
   por acidente;
2. **o valor do Jaccard não distingue `split` de `grew`** (0,50 nos dois). Quem
   distingue é a FORMA do casamento bipartido: no split, uma comunidade antiga
   casa com duas novas. Por isso `match()` devolve a forma, não só o número.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field

# Limiar de relação. NÃO é configurável: um τ que o usuário pudesse mudar
# tornaria "este é o mesmo tema" uma promessa condicional, e a trilha de épocas
# deixaria de ser comparável com ela mesma.
TAU = 1.0 / 3.0

# Vocabulário FECHADO (RFC-001 §4.2). `merged` fica declarado e sem superfície:
# não foi observado na calibração — modularidade resiste a fundir cliques
# densos, e nenhuma interface deve pressupor que ele é comum.
EVENTS = ("born", "grew", "shrank", "merged", "split", "died")


def jaccard(a: set[str], b: set[str]) -> float:
    uniao = a | b
    return len(a & b) / len(uniao) if uniao else 0.0


def theme_id(members: set[str]) -> str:
    """Id OPACO, derivado dos membros do NASCIMENTO e nunca recalculado.

    Opaco de propósito: um id derivado da composição vigente voltaria a mudar
    quando a composição muda, e `grew` nunca existiria — seria sempre um tema
    novo. Quem preserva a identidade através de `grew`/`shrank` é o casamento,
    não o id."""
    digest = hashlib.sha256("\n".join(sorted(members)).encode()).hexdigest()
    return "thm_" + digest[:12]


@dataclass
class ThemeEvent:
    """Um evento de época. `theme_id` vazio significa tema NOVO — quem escreve
    decide o id, porque só ele sabe os membros definitivos."""
    event: str
    members: set[str]
    theme_id: str = ""
    jaccard: float | None = None
    related: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.event not in EVENTS:
            raise ValueError(f"evento fora do vocabulário fechado: {self.event}")


def match(anteriores: dict[str, set[str]],
          novas: list[set[str]]) -> list[ThemeEvent]:
    """Casa a época anterior com a nova e classifica pela FORMA.

    `anteriores` é {theme_id: membros}; `novas` é a partição nova (sem
    identidade ainda). Determinístico: pares ordenados por (-jaccard,
    theme_id, índice), então empate nunca decide por ordem de dicionário.

    A classificação segue a tabela do RFC-001 §4.2. Um detalhe que só a
    medição revela: `1↔1 com membros idênticos` NÃO gera evento. Sem isso, toda
    execução do job registraria uma época para cada tema e a trilha viraria
    ruído — a mesma armadilha do rótulo que trocava a cada execução (ADR-43).
    """
    pares = sorted(
        ((jaccard(antigos, novos_membros), tid, i)
         for tid, antigos in anteriores.items()
         for i, novos_membros in enumerate(novas)
         if jaccard(antigos, novos_membros) >= TAU),
        key=lambda p: (-p[0], p[1], p[2]))

    por_antiga: dict[str, list[tuple[float, int]]] = {}
    por_nova: dict[int, list[tuple[float, str]]] = {}
    for j, tid, i in pares:
        por_antiga.setdefault(tid, []).append((j, i))
        por_nova.setdefault(i, []).append((j, tid))

    eventos: list[ThemeEvent] = []
    novas_consumidas: set[int] = set()

    for tid, antigos in sorted(anteriores.items()):
        casos = por_antiga.get(tid, [])
        if not casos:
            eventos.append(ThemeEvent("died", set(antigos), theme_id=tid))
            continue
        if len(casos) > 1:
            # 1 antiga → N novas: SPLIT. A mãe é supersedida pelas filhas, e
            # cada filha nasce com id próprio — não herdar o id é o ponto: as
            # duas metades não são "o mesmo tema que antes".
            filhas = [i for _, i in casos]
            novas_consumidas.update(filhas)
            eventos.append(ThemeEvent(
                "split", set(antigos), theme_id=tid,
                jaccard=max(j for j, _ in casos),
                related=[theme_id(novas[i]) for i in sorted(filhas)]))
            for i in sorted(filhas):
                eventos.append(ThemeEvent(
                    "born", set(novas[i]), theme_id=theme_id(novas[i]),
                    jaccard=jaccard(antigos, novas[i]), related=[tid]))
            continue
        j, i = casos[0]
        outras = [t for _, t in por_nova.get(i, []) if t != tid]
        if outras:
            # N antigas → 1 nova: MERGED. Herda o id da de MAIOR interseção;
            # as demais são supersedidas por ela. Ramo declarado e NÃO
            # observado na calibração (RFC-001 §2.3).
            melhor = max(por_nova[i], key=lambda p: (p[0], p[1]))[1]
            if tid != melhor:
                continue                    # tratado quando `melhor` chegar
            novas_consumidas.add(i)
            eventos.append(ThemeEvent(
                "merged", set(novas[i]), theme_id=tid, jaccard=j,
                related=sorted(outras)))
            for perdedora in sorted(outras):
                eventos.append(ThemeEvent(
                    "died", set(anteriores[perdedora]),
                    theme_id=perdedora, related=[tid]))
            continue
        novas_consumidas.add(i)
        if novas[i] == antigos:
            continue                        # nada mudou: nenhum evento
        eventos.append(ThemeEvent(
            "grew" if len(novas[i]) > len(antigos) else "shrank",
            set(novas[i]), theme_id=tid, jaccard=j))

    for i, membros in enumerate(novas):
        if i not in novas_consumidas and i not in por_nova:
            eventos.append(ThemeEvent("born", set(membros),
                                      theme_id=theme_id(membros)))
    return eventos
