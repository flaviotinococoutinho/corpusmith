-- index.db — derivado, sempre reconstruível a partir do bundle (okf index)
CREATE TABLE IF NOT EXISTS chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page       TEXT NOT NULL,      -- rel_path da página OKF
    ord        INTEGER NOT NULL,
    text       TEXT NOT NULL,
    resource   TEXT,
    privacy    TEXT,
    stale      INTEGER NOT NULL DEFAULT 0,
    valid_at   TEXT,               -- bi-temporalidade (v0.8 §6): tempo de MUNDO
    invalid_at TEXT
);
CREATE INDEX IF NOT EXISTS chunks_page ON chunks(page);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TABLE IF NOT EXISTS graph_edges (
    src  TEXT NOT NULL,
    dst  TEXT NOT NULL,
    kind TEXT NOT NULL,          -- 'wikilink' | 'markdown'
    confidence TEXT DEFAULT 'extracted',   -- v0.8 §1.4: extracted|inferred|ambiguous
    PRIMARY KEY (src, dst, kind)
);

CREATE TABLE IF NOT EXISTS communities (
    page      TEXT PRIMARY KEY,
    community INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id),
    model    TEXT NOT NULL,
    vec      BLOB NOT NULL
);

-- ============================ v0.8 (§2.1) ============================
-- anexo de entidades canônicas (controle de autoridade + detectores)
CREATE TABLE IF NOT EXISTS entities(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, canonical TEXT NOT NULL,
  authority TEXT, qid TEXT, UNIQUE(kind, canonical));
CREATE TABLE IF NOT EXISTS page_entities(
  page TEXT NOT NULL, entity_id INTEGER NOT NULL REFERENCES entities(id),
  surface TEXT NOT NULL, n INTEGER DEFAULT 1,
  confidence TEXT DEFAULT 'extracted'
    CHECK(confidence IN ('extracted','inferred','ambiguous')),
  data TEXT,                       -- JSON: {"iso": "...", "si": {...}} quando houver
  PRIMARY KEY(page, entity_id, surface));
CREATE INDEX IF NOT EXISTS idx_pe_entity ON page_entities(entity_id);

-- L0/L1 para descida hierárquica (L2 = chunks existentes)
CREATE TABLE IF NOT EXISTS page_levels(
  page TEXT NOT NULL, level INTEGER NOT NULL CHECK(level IN (0,1)),
  text TEXT NOT NULL, PRIMARY KEY(page, level));
CREATE VIRTUAL TABLE IF NOT EXISTS fts_levels USING fts5(
    text, content='page_levels'
);
CREATE TRIGGER IF NOT EXISTS page_levels_ai AFTER INSERT ON page_levels BEGIN
    INSERT INTO fts_levels(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS page_levels_ad AFTER DELETE ON page_levels BEGIN
    INSERT INTO fts_levels(fts_levels, rowid, text) VALUES ('delete', old.rowid, old.text);
END;

-- pontes frágeis do grafo (persistência 0-dim, v0.9) — recomputável no leiden
CREATE TABLE IF NOT EXISTS graph_bridges(
  src TEXT NOT NULL, dst TEXT NOT NULL, weight REAL NOT NULL,
  small_side INTEGER NOT NULL, large_side INTEGER NOT NULL,
  PRIMARY KEY(src, dst));

-- overlay derivado do reflect (§8), recomputável
CREATE TABLE IF NOT EXISTS page_overlay(
  page TEXT PRIMARY KEY,
  status TEXT CHECK(status IN ('preferred','tentative','contested')),
  useful INTEGER DEFAULT 0, dead INTEGER DEFAULT 0, updated REAL);
