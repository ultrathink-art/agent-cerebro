"""SQLite schema management for long-term memory."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_MEMORY_HOME = os.path.expanduser("~/.agent-cerebro")
DB_NAME = "memory.sqlite3"

_connection: Optional[sqlite3.Connection] = None


def _resolve_memory_home() -> str:
    """Read AGENT_CEREBRO_HOME / AGENT_RECALL_HOME lazily (every call)."""
    return (
        os.environ.get("AGENT_CEREBRO_HOME", "").strip()
        or os.environ.get("AGENT_RECALL_HOME", "").strip()
        or DEFAULT_MEMORY_HOME
    )


def get_db_path(memory_home: Optional[str] = None) -> str:
    """Resolve path to the SQLite database."""
    home = memory_home or _resolve_memory_home()
    return os.path.join(home, DB_NAME)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            category TEXT NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB,
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_role_category ON entries(role, category)
    """)
    conn.commit()


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get or create a SQLite connection with schema initialized."""
    global _connection

    path = db_path or get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    if _connection is not None:
        try:
            _connection.execute("SELECT 1")
            return _connection
        except sqlite3.ProgrammingError:
            _connection = None

    conn = sqlite3.connect(path)
    ensure_schema(conn)

    if db_path is None:
        _connection = conn

    return conn


def reset_connection() -> None:
    """Close and clear the cached connection (for testing)."""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass
        _connection = None
