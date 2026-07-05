"""FTS5 sobre chunks + reconstrução do index.db a partir do bundle
(Parte V §7.2, estendido na v0.8 §6.1c). O index.db é 100% derivado:
`rebuild_index` reconstrói chunks, arestas (com confiança §1.4), anexo de
entidades (page_entities), níveis L0/L1 (descida hierárquica) e cites do
page_heat — pode rodar a qualquer momento."""
from __future__ import annotations
import json
import re
import time
from ..okf.authorities import load_gazetteer
from ..okf.bundle import BundleReader
from ..okf.links import parse_links, is_internal, resolve
from ..normalize import analyze
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


def index_entities(idx, page: str, rep) -> None:
    """Grava o anexo estruturado de UMA página (§6.1c): entidades canônicas
    + valores (datas/quantidades ficam só aqui, nunca reescritas na prosa)."""
    idx.execute("DELETE FROM page_entities WHERE page=?", (page,))
    for m in rep.matches:
        if m.confidence == "ambiguous":
            continue
        idx.execute("INSERT OR IGNORE INTO entities(kind, canonical, authority, qid)"
                    " VALUES (?,?,?,?)",
                    (m.subkind, m.canonical, m.kind, (m.data or {}).get("qid")))
        eid = idx.execute("SELECT id FROM entities WHERE kind=? AND canonical=?",
                          (m.subkind, m.canonical)).fetchone()["id"]
        idx.execute("INSERT INTO page_entities(page, entity_id, surface, n, "
                    "confidence, data) VALUES (?,?,?,1,?,?) "
                    "ON CONFLICT(page, entity_id, surface) "
                    "DO UPDATE SET n = n + 1",
                    (page, eid, m.surface, m.confidence,
                     json.dumps(m.data) if m.data else None))


def index_levels(idx, page: str, body: str, meta) -> None:
    """L0 = descrição/título · L1 = headings (L2 = chunks)."""
    idx.execute("DELETE FROM page_levels WHERE page=?", (page,))
    idx.execute("INSERT INTO page_levels VALUES (?,0,?)",
                (page, meta.description or meta.title or page))
    heads = " · ".join(re.findall(r"^#{1,3}\s+(.+)$", body, re.M)[:12])
    idx.execute("INSERT INTO page_levels VALUES (?,1,?)",
                (page, heads or (meta.description or meta.title or page)))


def rebuild_index(s: Settings) -> dict:
    kb = s.path("knowledge")
    reader = BundleReader(kb / "bundle")
    gaz = load_gazetteer(reader)
    idx = connect(s.app_support / "index.db")
    idx.execute("DELETE FROM chunks")
    idx.execute("DELETE FROM graph_edges")
    pages = 0
    in_links: dict[str, int] = {}
    for d in reader.iter_concepts():
        pages += 1
        x = d.meta.model_dump(exclude_none=True, mode="json")
        for i, text in enumerate(_chunk(d.body)):
            idx.execute(
                "INSERT INTO chunks(page,ord,text,resource,privacy,stale,"
                "valid_at,invalid_at) VALUES (?,?,?,?,?,?,?,?)",
                (d.rel_path, i, text, d.meta.resource,
                 x.get("privacy"), int(bool(x.get("stale_as_of"))),
                 x.get("valid_at"), x.get("invalid_at")))
        for link in parse_links(d.body):
            if is_internal(link.target):
                dst = resolve(link.target, d.rel_path)
                conf = "extracted" if link.kind == "markdown" else "ambiguous"
                idx.execute(
                    "INSERT OR IGNORE INTO graph_edges(src,dst,kind,confidence)"
                    " VALUES (?,?,?,?)", (d.rel_path, dst, link.kind, conf))
                in_links[dst] = in_links.get(dst, 0) + 1
        rep = analyze(d.body, gaz=gaz)
        index_entities(idx, d.rel_path, rep)
        index_levels(idx, d.rel_path, d.body, d.meta)
    idx.commit()
    chunks = idx.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    idx.close()

    # cites → page_heat (alimenta o reflect, §8)
    rt = connect(s.app_support / "runtime.db")
    now = time.time()
    for page, n in in_links.items():
        rt.execute("INSERT INTO page_heat(path, cites, last_seen, first_seen) "
                   "VALUES (?,?,?,?) ON CONFLICT(path) DO UPDATE SET cites=?, "
                   "first_seen = COALESCE(first_seen, ?)",
                   (page, n, now, now, n, now))
    rt.commit()
    rt.close()
    return {"pages": pages, "chunks": chunks}


# stopwords pt/en: OR sobre elas casa qualquer página e mata a ABSTENÇÃO
STOPWORDS = {
    "de", "do", "da", "dos", "das", "o", "a", "os", "as", "um", "uma", "uns",
    "umas", "em", "no", "na", "nos", "nas", "com", "por", "para", "pra",
    "que", "qual", "quais", "como", "quando", "onde", "quem", "e", "ou",
    "se", "ao", "aos", "foi", "ser", "sao", "são", "era", "sobre", "entre",
    "mais", "menos", "muito", "ja", "já", "nao", "não", "usa", "usamos",
    "the", "of", "in", "on", "at", "to", "for", "and", "or", "a", "an",
    "is", "was", "are", "what", "which", "how", "when", "where", "who"}


def fts_terms(q: str) -> str:
    """Termos significativos da consulta (números sempre contam)."""
    terms = [t for t in re.findall(r"\w+", q)
             if t.isdigit() or (len(t) >= 3 and t.lower() not in STOPWORDS)]
    return " OR ".join(f'"{t}"' for t in terms) if terms else '""'


_fts_query = fts_terms


def search(s: Settings, query: str, *, limit: int = 8,
           local_only: bool = False) -> list[dict]:
    idx = connect(s.app_support / "index.db")
    sql = ("SELECT c.id, c.page, c.text, c.resource, c.privacy, c.stale, "
           "c.valid_at, c.invalid_at, bm25(chunks_fts) score FROM chunks_fts "
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
