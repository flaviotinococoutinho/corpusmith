"""FTS5 sobre chunks + reconstrução do index.db a partir do bundle
(Parte V §7.2). O index.db é 100% derivado: `rebuild_index` pode rodar a
qualquer momento (CLI `okf index`, pós-compile, pós-promote)."""
from __future__ import annotations
import re
from pathlib import Path
from ..okf.bundle import BundleReader
from ..okf.links import parse_links, is_internal, resolve
from ..runtime.db import connect
from ..settings import Settings

CHUNK_CHARS = 1200


def _chunk(body: str) -> list[str]:
    paras = re.split(r"\n{2,}", body)
    out: list[str] = []
    cur = ""
    for p in paras:
        if len(cur) + len(p) > CHUNK_CHARS and cur:
            out.append(cur.strip())
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur.strip():
        out.append(cur.strip())
    return out


def rebuild_index(s: Settings) -> dict:
    kb = s.path("knowledge")
    reader = BundleReader(kb / "bundle")
    idx = connect(s.app_support / "index.db")
    idx.execute("DELETE FROM chunks")
    idx.execute("DELETE FROM graph_edges")
    pages = 0
    for d in reader.iter_concepts():
        pages += 1
        x = d.meta.model_dump(exclude_none=True, mode="json")
        for i, text in enumerate(_chunk(d.body)):
            idx.execute(
                "INSERT INTO chunks(page,ord,text,resource,privacy,stale) "
                "VALUES (?,?,?,?,?,?)",
                (d.rel_path, i, text, d.meta.resource,
                 x.get("privacy"), int(bool(x.get("stale_as_of")))))
        for link in parse_links(d.body):
            if is_internal(link.target):
                idx.execute(
                    "INSERT OR IGNORE INTO graph_edges(src,dst,kind) VALUES (?,?,?)",
                    (d.rel_path, resolve(link.target, d.rel_path), link.kind))
    idx.commit()
    chunks = idx.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    idx.close()
    return {"pages": pages, "chunks": chunks}


def _fts_query(q: str) -> str:
    terms = re.findall(r"\w+", q)
    return " OR ".join(f'"{t}"' for t in terms) if terms else '""'


def search(s: Settings, query: str, *, limit: int = 8,
           local_only: bool = False) -> list[dict]:
    idx = connect(s.app_support / "index.db")
    sql = ("SELECT c.id, c.page, c.text, c.resource, c.privacy, c.stale, "
           "bm25(chunks_fts) score FROM chunks_fts "
           "JOIN chunks c ON c.id = chunks_fts.rowid "
           "WHERE chunks_fts MATCH ? ")
    args: list = [_fts_query(query)]
    if local_only:
        pass  # local_only restringe MODELO, não leitura do índice local
    sql += "ORDER BY score LIMIT ?"
    args.append(limit)
    try:
        rows = [dict(r) for r in idx.execute(sql, args)]
    finally:
        idx.close()
    return rows
