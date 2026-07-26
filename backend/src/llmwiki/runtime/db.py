"""SQLite com WAL + schema idempotente por banco (Parte V §5.2).

`connect()` é a ÚNICA porta de acesso — aplica o schema correspondente ao
nome do arquivo (runtime.db / index.db) em toda conexão (CREATE IF NOT
EXISTS), então qualquer consumidor pode conectar sem cerimônia.
"""
from __future__ import annotations
import sqlite3
import threading
from pathlib import Path

# §19 (ADR-39): inicialização (schema idempotente + migrações + carimbo)
# roda UMA vez por (processo, arquivo); aberturas seguintes só aplicam
# PRAGMAs. Corta o custo fixo de toda conexão nos hot paths sem mudar a
# semântica: o primeiro connect() de cada banco continua fazendo tudo.
_INITIALIZED: set[str] = set()
_INIT_LOCK = threading.Lock()

_SQL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "db"

_SCHEMAS = {
    "runtime.db": "schema_runtime.sql",
    "index.db": "schema_index.sql",
    "cold.db": "schema_cold.sql",
    "cognitive.db": "schema_cognitive.sql",   # experiência (v0.19) — separado
    "reference.db": "schema_reference.sql",   # referência do mundo (v0.22)
}

# Versão de schema POR BANCO (v1.2): incrementar a cada mudança de forma.
# Carimbada em _meta em toda conexão; o manifesto de backup a registra e o
# restore em versão mais nova é seguro por construção (connect() reaplica
# CREATE IF NOT EXISTS + _migrate idempotente ao abrir o banco restaurado).
SCHEMA_VERSIONS = {
    "runtime.db": 8,     # + curation_acts (ato humano, F1-PR1)
    "index.db": 8,       # + graph_centrality (Brandes fora do request)
    "cold.db": 1,
    "cognitive.db": 2,   # v0.19 base + v0.20 experiências/analogias
    "reference.db": 1,
}


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()          # arquivo apagado ⇒ re-inicializa
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    schema = _SCHEMAS.get(path.name)
    key = str(path.resolve())
    if schema and not existed:
        with _INIT_LOCK:
            _INITIALIZED.discard(key)  # recriado do zero: reinicializa
    if schema:
        conn.execute("CREATE TABLE IF NOT EXISTS _meta("
                     "key TEXT PRIMARY KEY, value TEXT)")
        # REJEITA banco de versão FUTURA antes de escrever nada (v1.4):
        # abrir um DB de um produto mais novo e recarimbá-lo para baixo
        # corromperia dados que este código não entende. Esta checagem
        # roda em TODA abertura (um SELECT indexado — barato); só a
        # inicialização pesada abaixo é 1×/processo (§19, ADR-39).
        stamped = conn.execute("SELECT value FROM _meta WHERE "
                               "key='schema_version'").fetchone()
        wanted = SCHEMA_VERSIONS[path.name]
        if stamped is not None and int(stamped["value"]) > wanted:
            conn.close()
            raise SchemaTooNewError(
                f"{path.name}: schema v{stamped['value']} é MAIS NOVO que "
                f"este produto suporta (v{wanted}) — atualize o llmwiki")
        if existed and key in _INITIALIZED:
            return conn                # abertura comum: PRAGMAs + guarda
        conn.executescript((_SQL_DIR / schema).read_text())
        _migrate(conn, path.name)
        # ledger de migração (v1.4): registra from→to quando a versão
        # carimbada muda — trilha auditável, não só o número final
        if stamped is None or int(stamped["value"]) != wanted:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "from_version INTEGER, to_version INTEGER, "
                "applied_at REAL DEFAULT (unixepoch('subsec')))")
            try:
                conn.execute(
                    "INSERT INTO schema_migrations(from_version, to_version) "
                    "VALUES (?,?)",
                    (int(stamped["value"]) if stamped else None, wanted))
                conn.execute("INSERT OR REPLACE INTO _meta(key, value) "
                             "VALUES ('schema_version', ?)", (str(wanted),))
            except sqlite3.OperationalError:
                pass                    # advisory: outra conexão carimba
        conn.commit()
        with _INIT_LOCK:
            _INITIALIZED.add(key)
    return conn


def reset_initialized() -> None:
    """Volta ao caminho de inicialização completa (testes/restore: um
    banco restaurado por cima PRECISA repassar por schema+migração)."""
    with _INIT_LOCK:
        _INITIALIZED.clear()


class SchemaTooNewError(RuntimeError):
    """Banco gravado por uma versão MAIS NOVA do produto (v1.4)."""


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def _migrate(conn: sqlite3.Connection, name: str) -> None:
    """ALTERs para bancos criados por versões anteriores (CREATE IF NOT
    EXISTS não acrescenta colunas). Idempotente."""
    if name == "index.db":
        if "confidence" not in _columns(conn, "graph_edges"):
            conn.execute("ALTER TABLE graph_edges ADD COLUMN "
                         "confidence TEXT DEFAULT 'extracted'")
        chunk_cols = _columns(conn, "chunks")
        for col in ("valid_at", "invalid_at"):
            if col not in chunk_cols:
                conn.execute(f"ALTER TABLE chunks ADD COLUMN {col} TEXT")
        if "superseded" not in chunk_cols:      # INV-003 (v1.3)
            conn.execute("ALTER TABLE chunks ADD COLUMN "
                         "superseded INTEGER NOT NULL DEFAULT 0")
        pe_cols = _columns(conn, "page_entities")   # grounding por span (v1.8)
        for col in ("span_start", "span_end"):
            if col not in pe_cols:
                conn.execute(f"ALTER TABLE page_entities ADD COLUMN {col} "
                             "INTEGER")
        # F2-PR3+4: `graph_snapshot` nasceu na v7 sem o backend da
        # centralidade. `CREATE TABLE IF NOT EXISTS` não altera tabela que já
        # existe, então banco v7 precisa do ALTER — sem isto o snapshot antigo
        # continua sem a coluna e o carimbo falha na PRIMEIRA escrita.
        if "graph_snapshot" in _tables(conn) \
                and "centrality_backend" not in _columns(conn,
                                                         "graph_snapshot"):
            conn.execute("ALTER TABLE graph_snapshot ADD COLUMN "
                         "centrality_backend TEXT NOT NULL DEFAULT 'none'")
    if name == "runtime.db":
        if "first_seen" not in _columns(conn, "page_heat"):
            conn.execute("ALTER TABLE page_heat ADD COLUMN first_seen REAL")
            conn.execute("UPDATE page_heat SET first_seen = last_seen "
                         "WHERE first_seen IS NULL")
        if "page" not in _columns(conn, "compile_cache"):
            conn.execute("ALTER TABLE compile_cache ADD COLUMN page TEXT")
        # v0.12: o CHECK de reconcile_log ganha a operação RECYCLE
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' "
                           "AND name='reconcile_log'").fetchone()
        if row and "RECYCLE" not in row["sql"]:
            conn.executescript(
                "ALTER TABLE reconcile_log RENAME TO reconcile_log_old;"
                "CREATE TABLE reconcile_log("
                "  id INTEGER PRIMARY KEY, ts REAL DEFAULT (unixepoch('subsec')),"
                "  candidate TEXT,"
                "  op TEXT CHECK(op IN ('ADD','UPDATE','SUPERSEDE','NOOP',"
                "                       'RECYCLE')),"
                "  target TEXT, reason TEXT, signals TEXT);"
                "INSERT INTO reconcile_log "
                "  SELECT * FROM reconcile_log_old;"
                "DROP TABLE reconcile_log_old;")
