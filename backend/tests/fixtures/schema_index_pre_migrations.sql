-- Fixture de PROCESSO (PR-0): index.db como era ANTES das três migrações
-- por ALTER TABLE que `runtime/db.py::_migrate` aplica ao abrir o banco.
--
-- Congelado de propósito: `_migrate` decide por PRESENÇA DE COLUNA, nunca
-- por versão, então a única prova de que o caminho de UPGRADE funciona é
-- abrir um banco que realmente não tem as colunas. Não editar para
-- acompanhar o schema atual — se este arquivo virar cópia do
-- `db/schema_index.sql`, o teste para de provar qualquer coisa.
--
-- Ausências deliberadas (cada uma é uma migração a exercitar):
--   graph_edges.confidence          (v0.8 §1.4)
--   chunks.valid_at/invalid_at      (bi-temporalidade, v0.8 §6)
--   chunks.superseded               (INV-003, v1.3)
--   page_entities.span_start/end    (grounding, v1.8)

CREATE TABLE IF NOT EXISTS chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page       TEXT NOT NULL,
    ord        INTEGER NOT NULL,
    text       TEXT NOT NULL,
    resource   TEXT,
    privacy    TEXT,
    stale      INTEGER NOT NULL DEFAULT 0
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
    kind TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS entities(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, canonical TEXT NOT NULL,
  authority TEXT, qid TEXT, UNIQUE(kind, canonical));
CREATE TABLE IF NOT EXISTS page_entities(
  page TEXT NOT NULL, entity_id INTEGER NOT NULL REFERENCES entities(id),
  surface TEXT NOT NULL, n INTEGER DEFAULT 1,
  confidence TEXT DEFAULT 'extracted'
    CHECK(confidence IN ('extracted','inferred','ambiguous')),
  data TEXT,
  PRIMARY KEY(page, entity_id, surface));
CREATE INDEX IF NOT EXISTS idx_pe_entity ON page_entities(entity_id);

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

CREATE TABLE IF NOT EXISTS page_index_state(
  page TEXT PRIMARY KEY, sha TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS index_meta(
  key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS graph_bridges(
  src TEXT NOT NULL, dst TEXT NOT NULL, weight REAL NOT NULL,
  small_side INTEGER NOT NULL, large_side INTEGER NOT NULL,
  PRIMARY KEY(src, dst));

CREATE TABLE IF NOT EXISTS page_overlay(
  page TEXT PRIMARY KEY,
  status TEXT CHECK(status IN ('preferred','tentative','contested')),
  useful INTEGER DEFAULT 0, dead INTEGER DEFAULT 0, updated REAL);
