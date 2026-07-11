"""Identidade Snowflake (v0.16) — um inteiro de 63 bits que carrega a
história do próprio evento: QUANDO aconteceu, QUAL módulo o produziu e
QUAL algoritmo estava configurado no momento.

Layout (compatível com o Snowflake do Twitter/X em espírito — timestamp
nos bits altos preserva a ordenação temporal em qualquer índice B-tree,
inclusive como PRIMARY KEY do SQLite sem custo extra):

    bit 63        : 0 (sinal — o id cabe em INTEGER assinado)
    bits 62..22   : 41 bits — milissegundos desde EPOCH (2026-01-01 UTC)
    bits 21..16   :  6 bits — módulo emissor   (MODULES, 0..63)
    bits 15..10   :  6 bits — algoritmo ativo  (ALGORITHMS, 0..63)
    bits  9..0    : 10 bits — sequência por milissegundo (0..1023)

41 bits de milissegundos duram ~69 anos; 1024 ids/ms por (módulo,
algoritmo) está ordens de magnitude acima do throughput real do daemon.
Relógio que anda para trás não quebra a monotonicidade: o timestamp é
CLAMPADO ao último emitido e a sequência continua (mesma técnica do
snowflake original). Estouro de sequência no mesmo ms avança o timestamp
lógico em 1 ms — nunca bloqueia, nunca repete.

Puro: stdlib somente (time/threading/datetime); nenhum I/O.
"""
from __future__ import annotations
import threading
import time
from datetime import datetime, timezone

EPOCH_MS = 1_767_225_600_000            # 2026-01-01T00:00:00Z
_TS_BITS, _MODULE_BITS, _ALGO_BITS, _SEQ_BITS = 41, 6, 6, 10
_MODULE_SHIFT = _ALGO_BITS + _SEQ_BITS
_TS_SHIFT = _MODULE_BITS + _MODULE_SHIFT
_SEQ_MASK = (1 << _SEQ_BITS) - 1

# Registro canônico dos emissores — o número É o contrato (aparece dentro
# de ids persistidos; nunca renumerar, só acrescentar).
MODULES = {
    "unknown": 0, "ask": 1, "compile": 2, "consolidate": 3, "review": 4,
    "reflect": 5, "communities": 6, "freeze": 7, "recycle": 8,
    "config": 9, "job": 10, "daemon": 11, "ingest": 12, "eval": 13,
    "pipeline": 14, "focus": 15, "session": 16,
}
ALGORITHMS = {
    "none": 0, "rrf": 1, "ppr": 2, "actr": 3, "hedge": 4,
    "pairwise": 5, "lsh": 6, "mdl": 7, "leiden": 8,
}
_MODULE_NAMES = {v: k for k, v in MODULES.items()}
_ALGO_NAMES = {v: k for k, v in ALGORITHMS.items()}

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"   # Crockford base32 (sem ilou)


def render(snowflake: int) -> str:
    """13 chars base32 Crockford, zero-padded — ordena lexicograficamente
    na MESMA ordem numérica (13·5=65 ≥ 63 bits), então serve de chave de
    texto (ask_id, trace em logs) sem perder a ordenação temporal."""
    out = []
    for _ in range(13):
        out.append(_ALPHABET[snowflake & 31])
        snowflake >>= 5
    return "".join(reversed(out))


def unrender(text: str) -> int:
    value = 0
    for ch in text:
        value = (value << 5) | _ALPHABET.index(ch)
    return value


def parse(snowflake: int | str) -> dict:
    """Decodifica QUALQUER id emitido: instante, módulo, algoritmo, seq."""
    if isinstance(snowflake, str):
        snowflake = unrender(snowflake)
    ts_ms = (snowflake >> _TS_SHIFT) + EPOCH_MS
    module = (snowflake >> _MODULE_SHIFT) & ((1 << _MODULE_BITS) - 1)
    algorithm = (snowflake >> _SEQ_BITS) & ((1 << _ALGO_BITS) - 1)
    return {"ts_ms": ts_ms,
            "iso": datetime.fromtimestamp(ts_ms / 1000, timezone.utc)
                   .isoformat(timespec="milliseconds"),
            "module": _MODULE_NAMES.get(module, str(module)),
            "algorithm": _ALGO_NAMES.get(algorithm, str(algorithm)),
            "seq": snowflake & _SEQ_MASK}


class SnowflakeFactory:
    """Gerador thread-safe por (módulo, algoritmo). O caminho quente é
    UMA comparação + incremento sob lock — otimizado de propósito: ids
    são emitidos em todo stage de pipeline e toda consulta."""

    __slots__ = ("_prefix", "_lock", "_last_ms", "_seq")

    def __init__(self, module: str = "unknown", algorithm: str = "none"):
        self._prefix = ((MODULES[module] << _MODULE_SHIFT)
                        | (ALGORITHMS[algorithm] << _SEQ_BITS))
        self._lock = threading.Lock()
        self._last_ms = 0
        self._seq = 0

    def next_id(self, now_ms: int | None = None) -> int:
        with self._lock:
            now = (now_ms if now_ms is not None
                   else time.time_ns() // 1_000_000) - EPOCH_MS
            if now <= self._last_ms:              # clamp: relógio p/ trás
                now = self._last_ms
                self._seq += 1
                if self._seq > _SEQ_MASK:         # estouro: avança 1 ms lógico
                    now += 1
                    self._seq = 0
            else:
                self._seq = 0
            self._last_ms = now
            return (now << _TS_SHIFT) | self._prefix | self._seq

    def next_rendered(self, now_ms: int | None = None) -> str:
        return render(self.next_id(now_ms))


_FACTORIES: dict[tuple[str, str], SnowflakeFactory] = {}


def factory(module: str, algorithm: str = "none") -> SnowflakeFactory:
    """Gerador COMPARTILHADO por (módulo, algoritmo) — duas instâncias do
    mesmo caso de uso no mesmo processo tiram ids da mesma sequência
    (unicidade garantida). setdefault em dict é atômico sob o GIL."""
    return _FACTORIES.setdefault((module, algorithm),
                                 SnowflakeFactory(module, algorithm))
