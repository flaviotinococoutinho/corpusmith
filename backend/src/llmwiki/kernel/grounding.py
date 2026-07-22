"""Grounding por span (v1.8, R1 do plano docs/13) — núcleo PURO.

Localiza no texto as SUPERFÍCIES (formas como aparecem) das entidades da
pergunta, devolvendo os offsets [start, end) para destaque na evidência.
É a versão determinística e verificável a olho da proveniência (à la
langextract, mas sem LLM): o "por que este trecho fundamenta a resposta"
fica visível. Não decide relevância — só mostra ONDE o termo perguntado
aparece. Sem match ⇒ lista vazia (nenhum highlight forçado).

Regras: comparação sem acento e case-insensitive com FRONTEIRA de palavra
(evita casar "R" dentro de "Rust"); spans não se sobrepõem (o mais longo
vence no empate de início); ordenados por posição; teto de ocorrências
para não explodir em trechos longos.
"""
from __future__ import annotations
import re
import unicodedata

MAX_SPANS = 50


def _fold(text: str) -> str:
    """Minúsculas sem diacrítico, preservando comprimento (NFD e remoção
    de combining marks alteram índice — por isso dobra-se caractere a
    caractere para manter offset 1:1 com o texto original)."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)
        stripped = "".join(c for c in base
                           if unicodedata.category(c) != "Mn")
        out.append((stripped or ch)[0].lower())
    return "".join(out)


def _is_word(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def ground_spans(body: str, surfaces: set[str]) -> list[list[int]]:
    """[[start, end), ...] das ocorrências das `surfaces` em `body`,
    com fronteira de palavra, sem sobreposição, ordenadas e limitadas."""
    if not body or not surfaces:
        return []
    folded = _fold(body)
    n = len(folded)
    found: list[tuple[int, int]] = []
    for surface in surfaces:
        needle = _fold(surface.strip())
        if not needle:
            continue
        start = 0
        while True:
            i = folded.find(needle, start)
            if i < 0:
                break
            j = i + len(needle)
            left_ok = i == 0 or not (_is_word(folded[i - 1])
                                     and _is_word(folded[i]))
            right_ok = j >= n or not (_is_word(folded[j - 1])
                                      and _is_word(folded[j]))
            if left_ok and right_ok:
                found.append((i, j))
            start = i + 1
    if not found:
        return []
    # resolve sobreposição: início asc, comprimento desc; pula os cobertos
    found.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    spans: list[list[int]] = []
    last_end = -1
    for a, b in found:
        if a >= last_end:
            spans.append([a, b])
            last_end = b
            if len(spans) >= MAX_SPANS:
                break
    return spans
