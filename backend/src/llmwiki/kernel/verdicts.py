"""Vereditos sobre padrão computado — PURO (F3-PR2, P-3).

**Dois níveis, separados pelo invariante** (`docs/14` §P-3). Veredito sobre
objeto CANÔNICO mora no canônico (frontmatter: `answered_by`, `superseded_by`)
— é conteúdo, versionado em Git, com o rito de escrita completo. Veredito
sobre padrão COMPUTADO — "esta ponte não vale a pena", "esta contradição
candidata é falso positivo" — não pode morar lá: o padrão não é uma página, é
uma relação derivada que o job recomputa do zero a cada execução.

**A chave é o que este módulo existe para acertar.** O caminho óbvio seria
chavear pelo rótulo de comunidade que o Leiden devolve — e ele é um inteiro de
ÉPOCA: muda a cada execução, então o veredito de hoje suprimiria um padrão
diferente na semana que vem. A chave sai da EVIDÊNCIA CANÔNICA: os `rel_path`
envolvidos, ordenados, hasheados. Mesmas páginas ⇒ mesma chave, para sempre,
independente de quantas vezes o algoritmo rode ou de que número ele atribua.

**`until` em vez de DELETE.** Rejeitar é suprimir com prazo declarado, não
apagar: apagar a linha faria o item voltar na próxima recomputação (o job
reconstrói a tabela de padrões inteira) e não deixaria rastro do juízo. É a
mesma disciplina de `invalid_at` no canônico — invalidar-nunca-apagar vale
também para o que o produto pensa sobre os próprios padrões.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass

STATUS = ("accepted", "rejected", "deferred")


@dataclass(frozen=True, slots=True)
class Verdict:
    kind: str
    key: str
    status: str
    until: float | None
    pages: tuple[str, ...]
    note: str = ""
    decided_at: float = 0.0


def pattern_key(pages) -> str:
    """Chave estável de um padrão, derivada da evidência canônica.

    Ordenada e deduplicada: a ponte A↔B é o mesmo padrão que B↔A, e nenhuma
    fonte deve depender da ordem em que o algoritmo listou as pontas."""
    canonico = "\n".join(sorted(set(pages)))
    return hashlib.sha256(canonico.encode()).hexdigest()[:16]


def suprime(verdict: Verdict, agora: float) -> bool:
    """Este veredito esconde o item AGORA?

    `accepted` não suprime — aceitar uma ponte é motivo para agir sobre ela,
    não para escondê-la; quem a tira da fila é o ato de link, não o juízo."""
    if verdict.status not in ("rejected", "deferred"):
        return False
    return verdict.until is None or agora < verdict.until


def suprimidos(verdicts, agora: float) -> set[str]:
    """Chaves atualmente suprimidas — o que as fontes da fila devem pular."""
    return {v.key for v in verdicts if suprime(v, agora)}
