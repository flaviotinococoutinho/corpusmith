"""Busca densa opcional (Parte V §7.3): usa embeddings do index.db quando
existem (job `embed` + Ollama). Sem embeddings, retorna vazio e a fusão
segue só com FTS — degradação silenciosa e local-first.

UM espaço vetorial por vez (Q-33): só entram vetores do modelo de embedding
CONFIGURADO, o mesmo que embute a pergunta. Cosseno entre espaços
diferentes não mede nada — e `zip` truncava em silêncio o par de dimensões
diferentes, dando score a ele."""
from __future__ import annotations
import json
import math
from ..runtime.db import connect
from ..runtime.stages import StageProfile
from ..settings import Settings


class DimensionMismatch(ValueError):
    """Par (pergunta, vetor) de dimensões diferentes: espaços distintos."""


def _cos(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise DimensionMismatch(
            f"dimensões divergentes ({len(a)} × {len(b)}): cosseno entre "
            "espaços vetoriais diferentes não é medida")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def search(s: Settings, query: str, *, limit: int = 8,
           router=None, profile: StageProfile | None = None) -> list[dict]:
    idx = connect(s.app_support / "index.db")
    try:
        model = s.models["local"].get("embed", "nomic-embed-text")
        n = idx.execute("SELECT COUNT(*) c FROM embeddings WHERE model = ?",
                        (model,)).fetchone()["c"]
        if not n or router is None or not router.local_available():
            return []
        qvec = router.embed([query])[0]
        rows = idx.execute(
            "SELECT e.chunk_id, e.vec, c.page, c.text, c.resource, "
            "c.privacy, c.stale FROM embeddings e "
            "JOIN chunks c ON c.id = e.chunk_id WHERE e.model = ?",
            (model,)).fetchall()
        scored, mismatched = [], 0
        for r in rows:
            try:
                scored.append((_cos(qvec, json.loads(r["vec"])), dict(r)))
            except DimensionMismatch:
                # mesmo NOME, outra dimensão (re-pull, linha legada): o
                # filtro por modelo não separa. Sai o PAR, não o stream —
                # e a contagem viaja no perfil da consulta.
                mismatched += 1
        if profile is not None:
            profile.count("dense_dim_mismatch", mismatched)
        scored.sort(key=lambda t: -t[0])
        out = []
        for score, r in scored[:limit]:
            r["id"] = r.pop("chunk_id")
            r.pop("vec", None)
            r["score"] = score
            out.append(r)
        return out
    except Exception:
        return []
    finally:
        idx.close()
