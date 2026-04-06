"""Tests for SQLite schema management."""
import os
import sqlite3

import pytest

from agentrecall.core.schema import (
    ensure_schema,
    get_connection,
    get_db_path,
    reset_connection,
)


class TestSchema:
    def test_creates_entries_table(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite3")
        conn = sqlite3.connect(db_path)
        ensure_schema(conn)

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "entries" in table_names
        conn.close()

    def test_creates_index(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite3")
        conn = sqlite3.connect(db_path)
        ensure_schema(conn)

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = [i[0] for i in indexes]
        assert "idx_role_category" in index_names
        conn.close()

    def test_idempotent(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite3")
        conn = sqlite3.connect(db_path)
        ensure_schema(conn)
        ensure_schema(conn)

        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()[0]
        assert count == 1
        conn.close()

    def test_table_columns(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite3")
        conn = sqlite3.connect(db_path)
        ensure_schema(conn)

        columns = conn.execute("PRAGMA table_info(entries)").fetchall()
        col_names = [c[1] for c in columns]
        assert "id" in col_names
        assert "role" in col_names
        assert "category" in col_names
        assert "text" in col_names
        assert "embedding" in col_names
        assert "tags" in col_names
        assert "created_at" in col_names
        conn.close()


class TestGetConnection:
    def test_creates_db_file(self, tmp_path):
        db_path = str(tmp_path / "new.sqlite3")
        conn = get_connection(db_path)

        assert os.path.exists(db_path)
        conn.close()

    def test_creates_parent_dirs(self, tmp_path):
        db_path = str(tmp_path / "nested" / "dir" / "test.sqlite3")
        conn = get_connection(db_path)

        assert os.path.exists(db_path)
        conn.close()

    def test_schema_ready_on_connect(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite3")
        conn = get_connection(db_path)

        conn.execute(
            "INSERT INTO entries (role, category, text, created_at) VALUES (?, ?, ?, ?)",
            ("r", "c", "t", "2026-01-01"),
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        assert count == 1
        conn.close()


class TestGetDbPath:
    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("AGENT_CEREBRO_HOME", raising=False)
        monkeypatch.delenv("AGENT_RECALL_HOME", raising=False)
        path = get_db_path()
        assert path.endswith("memory.sqlite3")
        assert ".agent-cerebro" in path

    def test_empty_env_uses_fallback(self, monkeypatch):
        monkeypatch.setenv("AGENT_CEREBRO_HOME", "")
        monkeypatch.delenv("AGENT_RECALL_HOME", raising=False)
        path = get_db_path()
        assert ".agent-cerebro" in path

    def test_whitespace_env_uses_fallback(self, monkeypatch):
        monkeypatch.setenv("AGENT_CEREBRO_HOME", "  ")
        monkeypatch.delenv("AGENT_RECALL_HOME", raising=False)
        path = get_db_path()
        assert ".agent-cerebro" in path

    def test_recall_home_fallback(self, monkeypatch):
        monkeypatch.delenv("AGENT_CEREBRO_HOME", raising=False)
        monkeypatch.setenv("AGENT_RECALL_HOME", "/legacy/path")
        path = get_db_path()
        assert path == "/legacy/path/memory.sqlite3"

    def test_cerebro_home_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("AGENT_CEREBRO_HOME", "/primary")
        monkeypatch.setenv("AGENT_RECALL_HOME", "/legacy")
        path = get_db_path()
        assert path == "/primary/memory.sqlite3"

    def test_custom_path(self):
        path = get_db_path("/custom/dir")
        assert path == "/custom/dir/memory.sqlite3"


class TestResetConnection:
    def test_reset_clears_cache(self):
        reset_connection()
        # Should not raise
        reset_connection()
