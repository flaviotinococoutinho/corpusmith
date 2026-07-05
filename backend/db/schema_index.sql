-- index.db — derivado, sempre reconstruível a partir do bundle (okf index)
CREATE TABLE IF NOT EXISTS chunks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    page     TEXT NOT NULL,      -- rel_path da página OKF
    ord      INTEGER NOT NULL,
    text     TEXT NOT NULL,
    resource TEXT,
    privacy  TEXT,
    stale    INTEGER NOT NULL DEFAULT 0
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
