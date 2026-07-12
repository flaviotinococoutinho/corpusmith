-- reference.db (v0.22) — dados DETERMINÍSTICOS de referência do mundo,
-- relacionais e separados das outras estruturas (avaliação funcional):
-- "memória SUA → bundle; referência DO MUNDO → relacional".
-- Precedência na normalização: authority_record (bundle) > ref_* > seeds.

CREATE TABLE IF NOT EXISTS ref_terms(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL DEFAULT 'entity',   -- entity|person|standard|toponym
  aliases TEXT NOT NULL DEFAULT '[]',    -- json
  source TEXT,
  created_at REAL DEFAULT (unixepoch('subsec')));

CREATE TABLE IF NOT EXISTS ref_quotations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quote TEXT NOT NULL,
  author TEXT NOT NULL,
  source TEXT,
  norm TEXT NOT NULL UNIQUE,             -- normalizada p/ matching exato
  created_at REAL DEFAULT (unixepoch('subsec')));

CREATE TABLE IF NOT EXISTS ref_facts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK(kind IN ('law','equation','axiom','logic_rule')),
  name TEXT NOT NULL,
  statement TEXT NOT NULL,
  domain TEXT,
  created_at REAL DEFAULT (unixepoch('subsec')),
  UNIQUE(kind, name));
