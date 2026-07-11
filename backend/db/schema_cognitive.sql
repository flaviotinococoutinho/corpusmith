-- cognitive.db (v0.19) — estado do Cognitive Experience Domain.
-- SEPARADO por construção: nenhuma tabela daqui duplica conteúdo
-- canônico — só REFERÊNCIAS (page path) + estado cognitivo próprio.
-- Projeções são reconstruíveis (goal + policy snapshot ⇒ mesmo working
-- set sobre a mesma memória).

CREATE TABLE IF NOT EXISTS focus_goals(
  id TEXT PRIMARY KEY,               -- snowflake (módulo=focus)
  goal TEXT NOT NULL,                -- json validado (new_focus_goal)
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
  created_at REAL DEFAULT (unixepoch('subsec')),
  updated_at REAL DEFAULT (unixepoch('subsec')));

CREATE TABLE IF NOT EXISTS cognitive_projections(
  id TEXT PRIMARY KEY,               -- snowflake (módulo=focus)
  goal_id TEXT NOT NULL,
  policy TEXT NOT NULL,              -- snapshot da política usada (json)
  working_set TEXT NOT NULL,         -- projeção completa e explicada (json)
  trace_id TEXT,
  created_at REAL DEFAULT (unixepoch('subsec')));

CREATE TABLE IF NOT EXISTS cognitive_sessions(
  id TEXT PRIMARY KEY,               -- snowflake (módulo=session)
  goal_id TEXT NOT NULL,
  projection_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('active','suspended','completed')),
  session TEXT NOT NULL,             -- json (steps, capsule, working set…)
  trace_id TEXT,
  started_at REAL DEFAULT (unixepoch('subsec')),
  updated_at REAL DEFAULT (unixepoch('subsec')));

CREATE TABLE IF NOT EXISTS retrieval_attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  item TEXT NOT NULL,                -- referência à página canônica
  exercise TEXT NOT NULL,
  prompt TEXT, answer TEXT,
  confidence_before REAL NOT NULL,   -- SEMPRE antes de revelar (calibração)
  result TEXT NOT NULL CHECK(result IN ('success','partial','failure')),
  duration_s REAL, support_used INTEGER DEFAULT 0,
  created_at REAL DEFAULT (unixepoch('subsec')));

-- acessibilidade cognitiva: escada validada por prática — NUNCA é
-- confiança epistemológica (essa mora no frontmatter canônico)
CREATE TABLE IF NOT EXISTS accessibility(
  item TEXT PRIMARY KEY,
  level TEXT NOT NULL DEFAULT 'none',
  streak INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_result TEXT,
  updated_at REAL DEFAULT (unixepoch('subsec')));

CREATE TABLE IF NOT EXISTS review_schedules(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item TEXT NOT NULL,
  due_at REAL NOT NULL,
  interval_days REAL NOT NULL,
  horizon_days INTEGER,
  algorithm TEXT NOT NULL DEFAULT 'spaced-v1',
  params TEXT, reason TEXT,
  status TEXT NOT NULL DEFAULT 'due' CHECK(status IN ('due','done','cancelled')),
  completed_at REAL,
  created_at REAL DEFAULT (unixepoch('subsec')));
CREATE INDEX IF NOT EXISTS reviews_due ON review_schedules(status, due_at);

-- feedback: EVENTO imutável (só INSERT; nenhum UPDATE no código)
CREATE TABLE IF NOT EXISTS cognitive_feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  scope TEXT NOT NULL, target TEXT,
  verdict TEXT NOT NULL, note TEXT,
  created_at REAL DEFAULT (unixepoch('subsec')));
