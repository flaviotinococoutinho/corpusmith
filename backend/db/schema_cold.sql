-- cold.db — a BASE FRIA (v0.12): memórias esquecidas, compactadas por MDL.
-- O digest (o "modelo": título, headings, entidades, ids fortes) fica
-- descomprimido e indexável para o recall de fallback; o corpo integral
-- (o "resíduo") vai comprimido em zlib. Esquecer compacta — nunca destrói:
-- Git guarda a história e recycle reidrata byte a byte.
CREATE TABLE IF NOT EXISTS cold_memories(
  page          TEXT PRIMARY KEY,      -- rel_path original no bundle
  digest        TEXT NOT NULL,         -- resumo indexável (FTS)
  strong_ids    TEXT NOT NULL DEFAULT '',  -- ids fortes (reconciliação/RECYCLE)
  body_z        BLOB NOT NULL,         -- corpo integral, zlib nível 9
  body_bytes    INTEGER NOT NULL,      -- tamanho original (métrica de ratio)
  meta_json     TEXT NOT NULL,         -- frontmatter completo
  frozen_at     REAL NOT NULL,
  frozen_commit TEXT,                  -- commit do freeze (auditoria)
  activation    REAL,                  -- B (BLA) no momento do freeze
  recall_p      REAL,                  -- P(recall) que validou o esquecimento
  reason        TEXT,
  recycles      INTEGER NOT NULL DEFAULT 0,
  last_recall   REAL);

CREATE VIRTUAL TABLE IF NOT EXISTS cold_fts USING fts5(
    digest, content='cold_memories'
);
CREATE TRIGGER IF NOT EXISTS cold_ai AFTER INSERT ON cold_memories BEGIN
    INSERT INTO cold_fts(rowid, digest) VALUES (new.rowid, new.digest);
END;
CREATE TRIGGER IF NOT EXISTS cold_ad AFTER DELETE ON cold_memories BEGIN
    INSERT INTO cold_fts(cold_fts, rowid, digest)
    VALUES ('delete', old.rowid, old.digest);
END;
