"""Tests for MemoryTimeline."""
import json
import sqlite3
from datetime import date, timedelta

import pytest

from agentrecall.core.timeline import MemoryTimeline, _parse_duration
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


class TestTimeline:
    def test_empty_returns_empty(self, tmp_db):
        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("nonexistent")
        assert result == []
        tl.close()

    def test_returns_entries_reverse_chronological(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "old entry", created_at="2026-01-01")
        _insert_entry(tmp_db, "coder", "gotchas", "new entry", created_at="2026-03-15")
        _insert_entry(tmp_db, "coder", "gotchas", "mid entry", created_at="2026-02-10")

        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("coder")
        assert len(result) == 3
        assert result[0]["text"] == "new entry"
        assert result[1]["text"] == "mid entry"
        assert result[2]["text"] == "old entry"
        tl.close()

    def test_filters_by_role(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "coder entry")
        _insert_entry(tmp_db, "social", "stories", "social entry")

        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("coder")
        assert len(result) == 1
        assert result[0]["text"] == "coder entry"
        tl.close()

    def test_filters_by_category(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "gotcha entry")
        _insert_entry(tmp_db, "coder", "fix_attempts", "fix entry")

        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("coder", category="gotchas")
        assert len(result) == 1
        assert result[0]["text"] == "gotcha entry"
        tl.close()

    def test_filters_by_last_duration(self, tmp_db):
        today = date.today()
        old_date = (today - timedelta(days=30)).isoformat()
        recent_date = (today - timedelta(days=2)).isoformat()

        _insert_entry(tmp_db, "coder", "gotchas", "old entry", created_at=old_date)
        _insert_entry(tmp_db, "coder", "gotchas", "recent entry", created_at=recent_date)

        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("coder", last="7d")
        assert len(result) == 1
        assert result[0]["text"] == "recent entry"
        tl.close()

    def test_limit_works(self, tmp_db):
        for i in range(10):
            _insert_entry(tmp_db, "coder", "gotchas", f"entry {i}",
                          created_at=f"2026-03-{i+1:02d}")

        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("coder", limit=3)
        assert len(result) == 3
        tl.close()

    def test_includes_tags(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "tagged entry", tags=["kamal", "docker"])

        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("coder")
        assert result[0]["tags"] == ["kamal", "docker"]
        tl.close()

    def test_entry_fields(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "test entry",
                      tags=["tag1"], created_at="2026-03-15")

        tl = MemoryTimeline(db_path=tmp_db)
        result = tl.timeline("coder")
        entry = result[0]
        assert "id" in entry
        assert entry["role"] == "coder"
        assert entry["category"] == "gotchas"
        assert entry["text"] == "test entry"
        assert entry["tags"] == ["tag1"]
        assert entry["created_at"] == "2026-03-15"
        tl.close()


class TestParseDuration:
    def test_days(self):
        result = _parse_duration("7d")
        assert result == date.today() - timedelta(days=7)

    def test_weeks(self):
        result = _parse_duration("2w")
        assert result == date.today() - timedelta(weeks=2)

    def test_months(self):
        result = _parse_duration("3m")
        assert result == date.today() - timedelta(days=90)

    def test_invalid_returns_none(self):
        assert _parse_duration("abc") is None
        assert _parse_duration("7x") is None
        assert _parse_duration("") is None
