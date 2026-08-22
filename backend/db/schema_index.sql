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
    invalid_at TEXT,
    superseded INTEGER NOT NULL DEFAULT 0   -- INV-003 (v1.3): fora do default
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
  span_start INTEGER,              -- offset da 1ª ocorrência no corpo (grounding v1.8)
  span_end INTEGER,
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

-- indexação INCREMENTAL (v0.13): sha por página + fingerprint do gazetteer
CREATE TABLE IF NOT EXISTS page_index_state(
  page TEXT PRIMARY KEY, sha TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS index_meta(
  key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- pontes frágeis do grafo (persistência 0-dim, v0.9) — recomputável no leiden
CREATE TABLE IF NOT EXISTS graph_bridges(
  src TEXT NOT NULL, dst TEXT NOT NULL, weight REAL NOT NULL,
  small_side INTEGER NOT NULL, large_side INTEGER NOT NULL,
  PRIMARY KEY(src, dst));

-- overlay derivado do reflect (§8), recomputável
CREATE TABLE IF NOT EXISTS page_overlay(
  page TEXT PRIMARY KEY,
  status TEXT CHECK(status IN ('preferred','tentative','low_yield')),
  useful INTEGER DEFAULT 0, dead INTEGER DEFAULT 0, updated REAL);

-- ============================ v1.9.1 · F2-PR1 (ADR-43) ============================
-- CARIMBO do snapshot da camada de padrões: o mapa passa a dizer DE QUANDO é e
-- COMO foi produzido. Uma linha só (`id=1`), sobrescrita a cada execução —
-- projeção 100% derivada, como todo o index.db (INV-002).
--
-- `backend` importa mais do que parece numa máquina onde o extra [ml] não
-- compilou: hoje o produto cai no fallback de componentes conexos EM SILÊNCIO e
-- chama o resultado de "comunidade". Registrar quem produziu o mapa é o que
-- permite o doctor dizer isso em voz alta (INV-004).
CREATE TABLE IF NOT EXISTS graph_snapshot(
  id            INTEGER PRIMARY KEY CHECK(id = 1),
  bundle_head   TEXT NOT NULL,      -- HEAD do Git quando o mapa foi computado
  computed_at   REAL NOT NULL,      -- epoch UTC
  backend       TEXT NOT NULL       -- 'leiden' | 'components'
                CHECK(backend IN ('leiden','components')),
  seed          INTEGER,            -- NULL só no fallback (não é aleatório)
  nodes         INTEGER NOT NULL,
  edges         INTEGER NOT NULL,
  communities   INTEGER NOT NULL,
  bridges       INTEGER NOT NULL,
  hubs_excluded INTEGER NOT NULL,
  -- F2-PR3+4: qual kernel mediu a centralidade. `none` = ainda não medida
  -- (o mapa existe, a centralidade não) — a interface serve grau em vez de
  -- inventar influência.
  centrality_backend TEXT NOT NULL DEFAULT 'none'
                CHECK(centrality_backend IN ('none','python','rust')));

-- ============================ v1.9.2 · F2-PR3+4 (ADR-44) ============================
-- CENTRALIDADE persistida. Brandes é 95% do custo do request do grafo a 1200
-- páginas (medido) e cresce ~O(n²): 100 páginas 25 ms, 1200 páginas 2571 ms,
-- 5000 páginas 88 s no baseline. Calcular no request dá data de morte ao
-- produto; e `structural_gaps` chamava `graph_data`, então abrir Grafo e
-- Insights pagava DUAS vezes.
--
-- Projeção como todo o index.db: sai no rebuild e é recomputada pelo job
-- `leiden`, junto do mapa — quem constrói o grafo é quem mede quem articula.
CREATE TABLE IF NOT EXISTS graph_centrality(
  page        TEXT PRIMARY KEY,
  betweenness REAL NOT NULL);

-- ============================ v1.9.3 · F2-PR2 (RFC-001, docs/16) ============================
-- IDENTIDADE de tema. O rótulo do ADR-43 é estável para o mesmo bundle mas é
-- derivado do menor membro: sai a página menor, muda o tema todo. Medido: um
-- tema de 5 páginas cuja página mais conectada troca passa a ter DUAS páginas
-- canônicas, nenhuma supersedida — o produto fabricando a contradição que o
-- `policy.contradiction_candidate` existe para acusar.
--
-- `theme_id` é OPACO de propósito: derivado da composição atual, voltaria a
-- mudar quando a composição muda, e nunca haveria `grew`.
CREATE TABLE IF NOT EXISTS themes(
  theme_id  TEXT PRIMARY KEY,
  community INTEGER,                 -- rótulo da época vigente (pode mudar)
  rel_path  TEXT NOT NULL,           -- communities/thm_<id>.md
  born_at   REAL NOT NULL,
  died_at   REAL,                    -- NULL = vivo
  members   TEXT NOT NULL);          -- JSON: membros da época vigente

-- Trilha das épocas. Vocabulário FECHADO — e `merged` fica declarado sem
-- superfície: não foi observado na calibração (RFC-001 §2.3), porque
-- modularidade resiste a fundir cliques densos.
CREATE TABLE IF NOT EXISTS theme_epochs(
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  theme_id    TEXT NOT NULL,
  event       TEXT NOT NULL
              CHECK(event IN ('born','grew','shrank','merged','split','died')),
  at          REAL NOT NULL,
  bundle_head TEXT,
  jaccard     REAL,                  -- casamento que gerou o evento
  members     TEXT,                  -- JSON dos membros nesta época
  related     TEXT);                 -- JSON: theme_id(s) envolvidos
CREATE INDEX IF NOT EXISTS idx_epochs_theme ON theme_epochs(theme_id);

-- RFC-006 V3: estabilidade EDITORIAL por página — projeção pura de
-- bundle+Git (kernel/stability.py consolida; ComputeStability escreve).
-- 'lifecycle' é o sentido de CICLO lido de vitality (viva | superseded_by
-- | invalid_at); 'edits' é o sentido de EDIÇÃO. Uso e tema têm donos
-- próprios (page_heat, theme_epochs) e NÃO entram aqui de propósito.
-- Frescor: checkpoint 'stability' em runtime.db (sobrevive ao rebuild).
CREATE TABLE IF NOT EXISTS page_stability(
  rel_path        TEXT PRIMARY KEY,
  edits           INTEGER NOT NULL,
  first_commit_at REAL,
  last_edit_at    REAL,
  lifecycle       TEXT NOT NULL DEFAULT 'viva',
  computed_from   TEXT NOT NULL);    -- HEAD do bundle na hora do cálculo
