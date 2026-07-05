"""SQLite com WAL + schema idempotente por banco (Parte V §5.2).

`connect()` é a ÚNICA porta de acesso — aplica o schema correspondente ao
nome do arquivo (runtime.db / index.db) em toda conexão (CREATE IF NOT
EXISTS), então qualquer consumidor pode conectar sem cerimônia.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

_SQL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "db"

_SCHEMAS = {
    "runtime.db": "schema_runtime.sql",
    "index.db": "schema_index.sql",
    "cold.db": "schema_cold.sql",
}


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    schema = _SCHEMAS.get(path.name)
    if schema:
        conn.executescript((_SQL_DIR / schema).read_text())
        _migrate(conn, path.name)
        conn.commit()
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


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
