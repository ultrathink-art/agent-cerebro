"""Tests for new CLI commands: timeline, export, stats, gc, search --tag."""
import json
import sqlite3
from datetime import date

import pytest

from agentrecall.cli import main
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


class TestCLITimelineHelp:
    def test_timeline_help(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["timeline", "--help"])
        assert exc_info.value.code == 0


class TestCLITimeline:
    def test_timeline_empty(self, tmp_db):
        with pytest.raises(SystemExit) as exc_info:
            main(["timeline", "nonexistent", "--db", tmp_db])
        assert exc_info.value.code == 1

    def test_timeline_with_entries(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "test entry", created_at="2026-03-15")

        with pytest.raises(SystemExit) as exc_info:
            main(["timeline", "coder", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "2026-03-15" in captured.out
        assert "test entry" in captured.out

    def test_timeline_with_last(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "old", created_at="2020-01-01")
        _insert_entry(tmp_db, "coder", "gotchas", "recent", created_at=date.today().isoformat())

        with pytest.raises(SystemExit) as exc_info:
            main(["timeline", "coder", "--last", "7d", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "recent" in captured.out
        assert "old" not in captured.out

    def test_timeline_with_category(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "gotcha entry")
        _insert_entry(tmp_db, "coder", "fixes", "fix entry")

        with pytest.raises(SystemExit) as exc_info:
            main(["timeline", "coder", "--category", "gotchas", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "gotcha entry" in captured.out
        assert "fix entry" not in captured.out


class TestCLIExportHelp:
    def test_export_help(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["export", "--help"])
        assert exc_info.value.code == 0


class TestCLIExport:
    def test_export_md(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "test entry", created_at="2026-03-15")

        with pytest.raises(SystemExit) as exc_info:
            main(["export", "coder", "--format", "md", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "# coder" in captured.out
        assert "test entry" in captured.out

    def test_export_json(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "test entry", created_at="2026-03-15")

        with pytest.raises(SystemExit) as exc_info:
            main(["export", "coder", "--format", "json", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["text"] == "test entry"

    def test_export_category_filter(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "gotcha")
        _insert_entry(tmp_db, "coder", "fixes", "fix")

        with pytest.raises(SystemExit) as exc_info:
            main(["export", "coder", "--category", "gotchas", "--format", "json", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1


class TestCLIStatsHelp:
    def test_stats_help(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["stats", "--help"])
        assert exc_info.value.code == 0


class TestCLIStats:
    def test_stats_empty(self, tmp_db, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["stats", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Total entries:" in captured.out
        assert "0" in captured.out

    def test_stats_with_role(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "entry1")

        with pytest.raises(SystemExit) as exc_info:
            main(["stats", "coder", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "coder" in captured.out

    def test_stats_all_roles(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "e1")
        _insert_entry(tmp_db, "social", "stories", "e2")

        with pytest.raises(SystemExit) as exc_info:
            main(["stats", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "2" in captured.out


class TestCLIGCHelp:
    def test_gc_help(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["gc", "--help"])
        assert exc_info.value.code == 0


class TestCLIGC:
    def test_gc_no_duplicates(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "unique entry")

        with pytest.raises(SystemExit) as exc_info:
            main(["gc", "coder", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "No duplicates" in captured.out

    def test_gc_dry_run(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "same text")
        _insert_entry(tmp_db, "coder", "gotchas", "same text")

        with pytest.raises(SystemExit) as exc_info:
            main(["gc", "coder", "--dry-run", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "1 duplicate" in captured.out

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.close()
        assert count == 2

    def test_gc_apply(self, tmp_db, capsys):
        _insert_entry(tmp_db, "coder", "gotchas", "same text")
        _insert_entry(tmp_db, "coder", "gotchas", "same text")

        with pytest.raises(SystemExit) as exc_info:
            main(["gc", "coder", "--apply", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "APPLIED" in captured.out
        assert "Removed 1" in captured.out

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.close()
        assert count == 1

    def test_gc_default_is_dry_run(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "same text")
        _insert_entry(tmp_db, "coder", "gotchas", "same text")

        with pytest.raises(SystemExit) as exc_info:
            main(["gc", "coder", "--db", tmp_db])
        assert exc_info.value.code == 0

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.close()
        assert count == 2


class TestCLISearchTag:
    def test_search_with_tag_filter(self, tmp_db, monkeypatch, capsys):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["store", "test", "cat", "deploy order loss", "--tags", "critical,deploy", "--db", tmp_db])
        assert exc_info.value.code == 0

        with pytest.raises(SystemExit) as exc_info:
            main(["store", "test", "cat", "sticker design issue", "--tags", "design", "--db", tmp_db])
        assert exc_info.value.code == 0

        capsys.readouterr()

        with pytest.raises(SystemExit) as exc_info:
            main(["search", "test", "cat", "deploy design", "--tag", "critical", "--db", tmp_db])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "deploy order loss" in captured.out
        assert "sticker design" not in captured.out

    def test_search_tag_no_match(self, tmp_db, monkeypatch):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["store", "test", "cat", "deploy order loss", "--tags", "deploy", "--db", tmp_db])
        assert exc_info.value.code == 0

        with pytest.raises(SystemExit) as exc_info:
            main(["search", "test", "cat", "deploy", "--tag", "nonexistent", "--db", tmp_db])
        assert exc_info.value.code == 1
