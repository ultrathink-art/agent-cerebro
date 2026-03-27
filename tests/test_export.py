"""Tests for MemoryExport."""
import json
import sqlite3
from datetime import date

import pytest

from agentrecall.core.export import MemoryExport
from agentrecall.core.schema import ensure_schema


def _insert_entry(db_path, role, category, text, tags=None, created_at=None):
    conn = sqlite3.connect(db_path)
    ensure_schema(conn)
    created = created_at or date.today().isoformat()
    tags_json = json.dumps(tags or [])
    conn.execute(
        "INSERT INTO entries (role, category, text, tags, created_at) VALUES (?, ?, ?, ?, ?)",
        (role, category, text, tags_json, created),
    )
    conn.commit()
    conn.close()


class TestExportMarkdown:
    def test_empty_role(self, tmp_db):
        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("nonexistent", fmt="md")
        assert "# nonexistent" in output
        assert "No entries found" in output
        exp.close()

    def test_single_category(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry one", created_at="2026-03-01")
        _insert_entry(tmp_db, "coder", "gotchas", "entry two", created_at="2026-03-02")

        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("coder", fmt="md")
        assert "# coder" in output
        assert "## gotchas" in output
        assert "**2026-03-01**: entry one" in output
        assert "**2026-03-02**: entry two" in output
        exp.close()

    def test_multiple_categories(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "gotcha entry")
        _insert_entry(tmp_db, "coder", "fix_attempts", "fix entry")

        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("coder", fmt="md")
        assert "## fix_attempts" in output
        assert "## gotchas" in output
        exp.close()

    def test_category_filter(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "gotcha entry")
        _insert_entry(tmp_db, "coder", "fix_attempts", "fix entry")

        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("coder", fmt="md", category="gotchas")
        assert "## gotchas" in output
        assert "fix_attempts" not in output
        exp.close()

    def test_tags_in_markdown(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "tagged", tags=["kamal", "docker"])

        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("coder", fmt="md")
        assert "`[kamal, docker]`" in output
        exp.close()

    def test_no_tags_no_bracket(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "no tags")

        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("coder", fmt="md")
        assert "`[" not in output
        exp.close()


class TestExportJSON:
    def test_json_format(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry one",
                      tags=["tag1"], created_at="2026-03-01")

        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("coder", fmt="json")
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["text"] == "entry one"
        assert data[0]["tags"] == ["tag1"]
        assert data[0]["created_at"] == "2026-03-01"
        assert data[0]["role"] == "coder"
        assert data[0]["category"] == "gotchas"
        exp.close()

    def test_json_empty(self, tmp_db):
        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("nonexistent", fmt="json")
        data = json.loads(output)
        assert data == []
        exp.close()

    def test_json_category_filter(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "gotcha entry")
        _insert_entry(tmp_db, "coder", "fix_attempts", "fix entry")

        exp = MemoryExport(db_path=tmp_db)
        output = exp.export("coder", fmt="json", category="gotchas")
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["category"] == "gotchas"
        exp.close()
