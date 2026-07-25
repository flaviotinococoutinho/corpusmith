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
-- ============================ v0.18 (camada cognitiva) ============================
-- Estado contextual DECLARADO (CLT): nunca inferido — princípio 5.3 da
-- espec (sinal humano é de primeira classe) + restrição de privacidade.
CREATE TABLE IF NOT EXISTS cognitive_state(
  id INTEGER PRIMARY KEY, ts REAL DEFAULT (unixepoch('subsec')),
  load INTEGER NOT NULL CHECK(load BETWEEN 1 AND 5),
  focus INTEGER CHECK(focus BETWEEN 1 AND 5),
  energy INTEGER CHECK(energy BETWEEN 1 AND 5),
  time_available_min INTEGER, note TEXT);
-- Contexto de cada consulta: estratégia usada + carga vigente + confiança
-- (1 − uncertainty) — a matéria-prima da calibração e da metacognição.
CREATE TABLE IF NOT EXISTS ask_context(
  ask_id TEXT PRIMARY KEY, strategy TEXT NOT NULL,
  load INTEGER, confidence REAL);
-- Crédito Hedge por ESTRATÉGIA de explicação (mesmo laço dos streams).
CREATE TABLE IF NOT EXISTS strategy_weights(
  strategy TEXT PRIMARY KEY, weight REAL NOT NULL DEFAULT 1.0);
-- Observações metacognitivas: HIPÓTESES mineradas com gate humano —
-- aceitar pode aplicar `suggestion` (tune) pela linhagem de config.
CREATE TABLE IF NOT EXISTS metacog_observations(
  id INTEGER PRIMARY KEY, ts REAL DEFAULT (unixepoch('subsec')),
  kind TEXT NOT NULL,          -- strategy|load|calibration
  statement TEXT NOT NULL, support INTEGER, confidence REAL,
  evidence TEXT, suggestion TEXT,
  status TEXT NOT NULL DEFAULT 'proposed'
    CHECK(status IN ('proposed','accepted','rejected','suspended')));

-- Pipelines CONFIGURÁVEIS (v0.17): a orquestração é DADO, não código.
-- O spec (json) compõe jobs já registrados; o sanduíche epistêmico segue
-- DENTRO de cada job (o pipeline orquestra ACIMA do template, nunca o
-- substitui). Runs guardam o filme: estado por estágio + trace snowflake.
CREATE TABLE IF NOT EXISTS pipelines(
  name TEXT PRIMARY KEY,
  spec TEXT NOT NULL,          -- json {description, stages:[{job,payload,on_error}]}
  builtin INTEGER NOT NULL DEFAULT 0,
  created_at REAL DEFAULT (unixepoch('subsec')),
  updated_at REAL DEFAULT (unixepoch('subsec')));
CREATE TABLE IF NOT EXISTS pipeline_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline TEXT NOT NULL,
  trace_id TEXT,
  state TEXT NOT NULL DEFAULT 'running',  -- running|done|partial|failed
  stages TEXT NOT NULL DEFAULT '[]',      -- json [{job,state,span,ms,error}]
  started_at REAL DEFAULT (unixepoch('subsec')),
  finished_at REAL);

CREATE TABLE IF NOT EXISTS config_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL DEFAULT (unixepoch('subsec')),
  trace_id TEXT,               -- snowflake do ajuste (módulo=config)
  changes TEXT NOT NULL,       -- delta aplicado (json)
  snapshot TEXT NOT NULL,      -- seções TUNABLE completas após aplicar (json)
  source TEXT NOT NULL DEFAULT 'cockpit',  -- cockpit|cli|baseline|rollback
  note TEXT);

-- ============================ v1.6 (ADR-38) ============================
-- Generalization Envelopes: o CONTEXTO exato de cada avaliação — em que
-- regime um mecanismo foi medido e onde NÃO foi. Colunas JSON carregam
-- payload_schema_version (governança de JSON em coluna, spec §5.5).
CREATE TABLE IF NOT EXISTS evaluation_envelopes(
  id TEXT PRIMARY KEY,
  mechanism_id TEXT NOT NULL,
  contract_version TEXT,
  policy_version TEXT,
  product_version TEXT,
  bundle_head TEXT,
  dataset TEXT,
  dataset_sha256 TEXT,
  sample_size INTEGER NOT NULL DEFAULT 0,
  query_categories TEXT NOT NULL DEFAULT '[]',   -- json array
  languages TEXT NOT NULL DEFAULT '[]',          -- json array
  domains TEXT NOT NULL DEFAULT '[]',            -- json array
  temporal_range TEXT,
  metrics TEXT NOT NULL DEFAULT '{}',            -- json object
  confidence_intervals TEXT,                     -- json object|null
  known_exclusions TEXT NOT NULL DEFAULT '[]',   -- json array
  out_of_scope TEXT NOT NULL DEFAULT '[]',       -- json array
  eval_run_ids TEXT NOT NULL DEFAULT '[]',       -- json array de eval_runs.id
  evaluation_status TEXT NOT NULL
    CHECK(evaluation_status IN ('unevaluated','partially_evaluated',
                                'evaluated','drifted','invalidated')),
  payload_schema_version INTEGER NOT NULL DEFAULT 1,
  created_at REAL DEFAULT (unixepoch('subsec')));
CREATE INDEX IF NOT EXISTS idx_envelopes_mechanism
  ON evaluation_envelopes(mechanism_id, created_at);

-- atos de curadoria HUMANA (F1-PR1, ADR-41) — ÍNDICE de atos, não verdade
-- paralela: a autoridade do que aconteceu é o Git + log.md, por isso cada
-- linha guarda o commit. `undoes`/`undone_by` já nascem aqui para a fase
-- não precisar de uma segunda migração quando o undo entrar (F1-PR2).
CREATE TABLE IF NOT EXISTS curation_acts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  act TEXT NOT NULL,
  params TEXT NOT NULL DEFAULT '{}',   -- json: parâmetros do ato
  commit_sha TEXT,
  pages TEXT NOT NULL DEFAULT '[]',    -- json array de rel_paths
  created_at REAL DEFAULT (unixepoch('subsec')),
  undoes INTEGER REFERENCES curation_acts(id),      -- este ato desfaz…
  undone_by INTEGER REFERENCES curation_acts(id),   -- …e foi desfeito por
  origin_kind TEXT,                    -- D-G: de onde veio (fila, finding…)
  origin_key TEXT);
CREATE INDEX IF NOT EXISTS idx_curation_acts_created
  ON curation_acts(created_at);
