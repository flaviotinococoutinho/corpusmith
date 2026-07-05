"""Job `embed` (Parte V §7.1): embeddings dos chunks sem vetor, via Ollama.
Sem Ollama disponível, encerra silenciosamente — a busca segue só FTS."""
from __future__ import annotations
import json
from ..models.router import ModelRouter
from ..runtime.db import connect
from ..settings import Settings


def run(s: Settings, payload: dict, emit) -> dict:
    router = ModelRouter(s)
    if not router.local_available():
        return {"embedded": 0, "skipped": "ollama offline"}
    idx = connect(s.app_support / "index.db")
    rows = idx.execute(
        "SELECT c.id, c.text FROM chunks c "
        "LEFT JOIN embeddings e ON e.chunk_id = c.id "
        "WHERE e.chunk_id IS NULL LIMIT 256").fetchall()
    model = s.models["local"].get("embed", "nomic-embed-text")
    done = 0
    for row in rows:
        vec = router.embed([row["text"]])[0]
        idx.execute("INSERT OR REPLACE INTO embeddings(chunk_id,model,vec) "
                    "VALUES (?,?,?)", (row["id"], model, json.dumps(vec)))
        done += 1
        if done % 32 == 0:
            idx.commit()
            emit("embed.progress", {"done": done, "total": len(rows)})
    idx.commit()
    idx.close()
    return {"embedded": done}
