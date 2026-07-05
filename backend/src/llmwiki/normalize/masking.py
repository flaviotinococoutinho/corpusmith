from __future__ import annotations
import re

_CITATIONS_H = re.compile(r"^#{1,2}\s*Citations\s*$", re.M)

def protected_spans(text: str) -> list[tuple[int, int]]:
    """Regiões que NENHUM detector pode tocar (§1.2): cercas de código
    (inclusive não fechadas — protege até o fim), código inline, blockquotes,
    alvos de link e a seção # Citations inteira (verbatim de fontes)."""
    spans: list[tuple[int, int]] = []
    fences = [m.span() for m in re.finditer(r"```", text)]
    for i in range(0, len(fences) - 1, 2):
        spans.append((fences[i][0], fences[i + 1][1]))
    if len(fences) % 2:
        spans.append((fences[-1][0], len(text)))
    for m in re.finditer(r"`[^`\n]+`", text):
        spans.append(m.span())
    for m in re.finditer(r"^>.*$", text, re.M):
        spans.append(m.span())
    for m in re.finditer(r"\]\([^)\s]*\)", text):      # só o alvo (…) do link
        spans.append((m.start() + 2, m.end() - 1))
    c = _CITATIONS_H.search(text)
    if c:
        spans.append((c.start(), len(text)))
    return spans

def is_protected(spans: list[tuple[int, int]], a: int, b: int) -> bool:
    return any(a < e and b > s for s, e in spans)
