"""Registro de checkpoints — a casca de I/O do `kernel/checkpoints.py`.

**Mora em `runtime.db`, e a escolha importa.** O carimbo do índice não pode
viver DENTRO do índice: `rebuild_index` apaga e reconstrói, e um registro que
some junto com aquilo que ele descreve não consegue dizer "esta derivação
sumiu". O `index_meta.bundle_head` de hoje tem exatamente esse limite — ele
diz de qual HEAD o índice veio quando o índice existe, e não diz nada quando
alguém apaga o arquivo. `runtime.db` é o banco que sobrevive ao rebuild.

O `detail` é JSON livre de propósito: cada derivação guarda o que serve para
ela (backend do particionamento, contagens, seed) sem que o registro precise
conhecer o vocabulário de todas. O que é NORMALIZADO é a relação — derivação,
fonte, estado da fonte, quando — e não o conteúdo.
"""
from __future__ import annotations
import json
import time
from ..kernel.checkpoints import (DERIVATIONS, Checkpoint, Staleness,
                                  evaluate)
from .db import connect

__all__ = ["record", "load", "current_states", "verify", "Checkpoint",
           "Staleness"]


def record(settings, derivation: str, input_state: str,
           detail: dict | None = None) -> Checkpoint:
    """Registra que `derivation` foi computada a partir de `input_state`.

    Recusa derivação não declarada em `DERIVATIONS`: registro dinâmico faria
    o doctor deixar de conhecer a cadeia, que é justamente o que este módulo
    existe para impedir."""
    if derivation not in DERIVATIONS:
        raise ValueError(
            f"derivação não declarada: {derivation!r} — acrescente em "
            f"kernel/checkpoints.py:DERIVATIONS, senão o doctor não a verifica")
    agora = time.time()
    corpo = json.dumps(detail or {}, default=str, sort_keys=True)
    rt = connect(settings.app_support / "runtime.db")
    try:
        rt.execute(
            "INSERT INTO checkpoints(derivation, input_state, computed_at, "
            "detail) VALUES (?,?,?,?) ON CONFLICT(derivation) DO UPDATE SET "
            "input_state=excluded.input_state, "
            "computed_at=excluded.computed_at, detail=excluded.detail",
            (derivation, input_state, agora, corpo))
        rt.commit()
    finally:
        rt.close()
    return Checkpoint(derivation, input_state, agora, corpo)


def load(settings) -> dict[str, Checkpoint]:
    rt = connect(settings.app_support / "runtime.db")
    try:
        linhas = [dict(r) for r in rt.execute(
            "SELECT derivation, input_state, computed_at, detail "
            "FROM checkpoints")]
    except Exception:
        return {}
    finally:
        rt.close()
    return {r["derivation"]: Checkpoint(
        r["derivation"], r["input_state"], r["computed_at"], r["detail"] or "")
        for r in linhas}


def current_states(settings) -> dict[str, str]:
    """Estado ATUAL de cada fonte.

    O bundle é lido do Git (autoridade). As demais fontes reportam o
    `input_state` do próprio checkpoint: a saída de uma derivação é a entrada
    da seguinte, e é isso que torna a cadeia verificável sem cada derivação
    inventar um fingerprint de saída."""
    from ..okf.authorities import _kb_head
    estados: dict[str, str] = {}
    head = _kb_head(settings.path("knowledge") / "bundle")
    estados["bundle"] = head or ""
    for nome, cp in load(settings).items():
        estados[nome] = cp.input_state
    return estados


def verify(settings) -> list[Staleness]:
    """Veredito de toda a cadeia — a função que o doctor chama.

    UMA regra para todas as derivações, em vez de um invariante por artefato.
    É o que faz a próxima derivação nascer com frescor verificado de graça."""
    return evaluate(load(settings), current_states(settings))
