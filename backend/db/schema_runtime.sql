-- runtime.db — fila de jobs, eventos, ledger de custos, cache de compilação
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    payload      TEXT NOT NULL DEFAULT '{}',
    priority     INTEGER NOT NULL DEFAULT 5,
    state        TEXT NOT NULL DEFAULT 'queued',  -- queued|leased|done|failed
    dedupe_key   TEXT UNIQUE,
    attempts     INTEGER NOT NULL DEFAULT 0,
    error        TEXT,
    result       TEXT,
    created_at   REAL NOT NULL,
    started_at   REAL,
    finished_at  REAL,
    leased_until REAL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state, priority DESC, created_at);

CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    channel    TEXT NOT NULL,
    type       TEXT NOT NULL,
    data       TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    provider   TEXT NOT NULL,
    model      TEXT NOT NULL,
    tokens_in  INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    usd        REAL NOT NULL DEFAULT 0,
    job_id     TEXT
);

CREATE TABLE IF NOT EXISTS compile_cache (
    source TEXT PRIMARY KEY,
    sha    TEXT NOT NULL,
    at     REAL NOT NULL,
    page   TEXT                -- destino da compilação (rastreio no Inbox, v0.11)
);

-- ============================ v0.8 (§2.1) ============================
CREATE TABLE IF NOT EXISTS ask_outcomes(
  id INTEGER PRIMARY KEY, ask_id TEXT, verdict TEXT NOT NULL
    CHECK(verdict IN ('useful','dead_end','corrected')),
  note TEXT, pages TEXT, ts REAL DEFAULT (unixepoch('subsec')));
CREATE TABLE IF NOT EXISTS page_heat(
  path TEXT PRIMARY KEY, reads INTEGER DEFAULT 0, cites INTEGER DEFAULT 0,
  last_seen REAL, first_seen REAL,     -- first_seen: vida L do BLA (v0.10)
  score REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS reconcile_log(        -- trilha de auditoria
  id INTEGER PRIMARY KEY, ts REAL DEFAULT (unixepoch('subsec')),
  candidate TEXT,
  op TEXT CHECK(op IN ('ADD','UPDATE','SUPERSEDE','NOOP','RECYCLE')),
  target TEXT, reason TEXT, signals TEXT);
CREATE TABLE IF NOT EXISTS eval_runs(
  id INTEGER PRIMARY KEY, ts REAL DEFAULT (unixepoch('subsec')),
  category TEXT, total INTEGER, passed INTEGER, detail TEXT);

-- ============================ v0.9 ============================
-- proveniência: qual stream de retrieval trouxe cada evidência de cada ask
CREATE TABLE IF NOT EXISTS ask_provenance(
  ask_id TEXT NOT NULL, page TEXT NOT NULL, stream TEXT NOT NULL,
  PRIMARY KEY(ask_id, page, stream));
-- crédito por stream (Hedge/multiplicative weights sobre os desfechos)
CREATE TABLE IF NOT EXISTS stream_weights(
  stream TEXT PRIMARY KEY, weight REAL NOT NULL DEFAULT 1.0);

-- ============================ v0.16 ============================
-- Configuração de negócio VERSIONADA em banco: ring buffer das últimas 30
-- entradas (a vigente é a mais recente; TuneConfig poda as excedentes).
-- Cada linha guarda o delta pedido E o snapshot completo pós-aplicação —
-- rollback é reaplicar o snapshot anterior, sem reconstruir deltas.
CREATE TABLE IF NOT EXISTS config_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL DEFAULT (unixepoch('subsec')),
  trace_id TEXT,               -- snowflake do ajuste (módulo=config)
  changes TEXT NOT NULL,       -- delta aplicado (json)
  snapshot TEXT NOT NULL,      -- seções TUNABLE completas após aplicar (json)
  source TEXT NOT NULL DEFAULT 'cockpit',  -- cockpit|cli|baseline|rollback
  note TEXT);
