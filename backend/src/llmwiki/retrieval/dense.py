"""Busca densa opcional (Parte V §7.3): usa embeddings do index.db quando
existem (job `embed` + Ollama). Sem embeddings, retorna vazio e a fusão
segue só com FTS — degradação silenciosa e local-first."""
from __future__ import annotations
import json
import math
from ..runtime.db import connect
from ..settings import Settings


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def search(s: Settings, query: str, *, limit: int = 8,
           router=None) -> list[dict]:
    idx = connect(s.app_support / "index.db")
    try:
        n = idx.execute("SELECT COUNT(*) c FROM embeddings").fetchone()["c"]
        if not n or router is None or not router.local_available():
            return []
        qvec = router.embed([query])[0]
        rows = idx.execute(
            "SELECT e.chunk_id, e.vec, c.page, c.text, c.resource, "
            "c.privacy, c.stale FROM embeddings e "
            "JOIN chunks c ON c.id = e.chunk_id").fetchall()
        scored = [(_cos(qvec, json.loads(r["vec"])), dict(r)) for r in rows]
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
