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
        conn.commit()
    return conn
