"""SimHash (v0.13) — sketch de similaridade em 64 bits.

Charikar, "Similarity Estimation Techniques from Rounding Algorithms"
(STOC 2002): a distância de Hamming entre simhashes aproxima a
dissimilaridade de conjuntos de features. Aqui, shingles de palavras
hasheados com blake2b (determinístico entre processos, ao contrário de
hash()). Uso: sinal barato de NEAR-DUPLICATA na consolidação por
recorrência — dois textos quase iguais convergem mesmo sem nenhuma
entidade curada em comum. É a estrutura de dados probabilística no
espírito das libs de layout (comparação O(1) no lugar de NCD O(n·zlib)).
"""
from __future__ import annotations
import hashlib
import re

BITS = 64


def _shingles(text: str, size: int) -> list[str]:
    words = re.findall(r"\w+", text.lower())
    if len(words) < size:
        return [" ".join(words)] if words else []
    return [" ".join(words[i:i + size]) for i in range(len(words) - size + 1)]


def simhash(text: str, *, shingle: int = 3) -> int:
    votes = [0] * BITS
    for piece in _shingles(text, shingle):
        digest = int.from_bytes(
            hashlib.blake2b(piece.encode(), digest_size=8).digest(), "big")
        for bit in range(BITS):
            votes[bit] += 1 if (digest >> bit) & 1 else -1
    value = 0
    for bit in range(BITS):
        if votes[bit] > 0:
            value |= 1 << bit
    return value


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def bands(value: int, *, count: int = 9, bits: int = BITS) -> tuple:
    """Bandas LSH do sketch (v0.16) — geração de pares candidatos EXATA.

    Casa de pombos: se dois hashes de 64 bits diferem em ≤ count−1 bits,
    fatiá-los em `count` bandas garante ao menos UMA banda idêntica —
    logo, indexar por (índice, valor) de banda recupera TODO par com
    hamming ≤ count−1 sem comparar os n² pares. Com count=9, cobre o
    limiar de near-duplicata da consolidação (hamming ≤ 8) sem falso
    negativo; falsos positivos são baratos (re-verificados por hamming).
    """
    edges = [round(i * bits / count) for i in range(count + 1)]
    return tuple(
        (i, (value >> edges[i]) & ((1 << (edges[i + 1] - edges[i])) - 1))
        for i in range(count))
