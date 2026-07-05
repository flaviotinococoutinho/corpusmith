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
    at     REAL NOT NULL
);
