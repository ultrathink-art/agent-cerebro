"""Tests for short-term memory file checking."""
import os

import pytest

from agentmemory.shortterm.check import (
    check_file,
    check_directory,
    count_session_log_entries,
    prune_session_log,
    MAX_LINES,
    MAX_SESSION_LOG_ENTRIES,
)


def _write_memory_file(path, line_count=40, session_entries=5):
    """Helper to create a memory file with controlled size."""
    lines = ["# Test Agent Memory\n", "\n", "## Mistakes\n"]
    lines.append("- [2026-01-01] Some mistake\n")
    lines.append("\n")
    lines.append("## Learnings\n")
    lines.append("- [2026-01-01] Some learning\n")
    lines.append("\n")
    lines.append("## Session Log\n")

    for i in range(session_entries):
        lines.append(f"- [2026-01-{i + 1:02d}] Session {i + 1}\n")

    lines.append("\n")
    lines.append("## Notes\n")

    while len(lines) < line_count:
        lines.append(f"Filler line {len(lines)}\n")

    with open(path, "w") as f:
        f.writelines(lines)
    return path


class TestCountSessionLogEntries:
    def test_counts_entries(self):
        lines = [
            "# Memory\n",
            "## Session Log\n",
            "- [2026-01-01] First\n",
            "- [2026-01-02] Second\n",
            "- [2026-01-03] Third\n",
        ]
        assert count_session_log_entries(lines) == 3

    def test_stops_at_next_section(self):
        lines = [
            "## Session Log\n",
            "- [2026-01-01] First\n",
            "## Other Section\n",
            "- [2026-01-02] Not counted\n",
        ]
        assert count_session_log_entries(lines) == 1

    def test_zero_entries(self):
        lines = ["# Memory\n", "## Mistakes\n", "- Something\n"]
        assert count_session_log_entries(lines) == 0

    def test_no_session_section(self):
        lines = ["# Memory\n", "## Mistakes\n"]
        assert count_session_log_entries(lines) == 0


class TestPruneSessionLog:
    def test_prunes_oldest(self):
        lines = [
            "## Session Log\n",
            "- [2026-01-05] Newest\n",
            "- [2026-01-04] Fourth\n",
            "- [2026-01-03] Third\n",
            "- [2026-01-02] Second\n",
            "- [2026-01-01] Oldest\n",
        ]
        pruned = prune_session_log(lines, 3)
        assert count_session_log_entries(pruned) == 3
        assert "- [2026-01-05] Newest\n" in pruned
        assert "- [2026-01-01] Oldest\n" not in pruned

    def test_no_pruning_needed(self):
        lines = [
            "## Session Log\n",
            "- [2026-01-01] Only one\n",
        ]
        pruned = prune_session_log(lines, 5)
        assert pruned == lines

    def test_no_session_section(self):
        lines = ["# Memory\n", "## Mistakes\n"]
        pruned = prune_session_log(lines, 5)
        assert pruned == lines


class TestCheckFile:
    def test_pass_under_limit(self, tmp_path):
        path = str(tmp_path / "test.md")
        _write_memory_file(path, line_count=40, session_entries=5)

        result = check_file(path)
        assert result.status == "PASS"
        assert not result.over_limit
        assert not result.session_warn

    def test_fail_over_limit(self, tmp_path):
        path = str(tmp_path / "test.md")
        _write_memory_file(path, line_count=100, session_entries=5)

        result = check_file(path)
        assert result.status == "FAIL"
        assert result.over_limit

    def test_warn_session_entries(self, tmp_path):
        path = str(tmp_path / "test.md")
        _write_memory_file(path, line_count=50, session_entries=20)

        result = check_file(path)
        assert result.session_warn

    def test_fix_prunes_sessions(self, tmp_path):
        path = str(tmp_path / "test.md")
        _write_memory_file(path, line_count=50, session_entries=20)

        result = check_file(path, fix=True)
        assert result.fixed
        assert result.new_line_count is not None
        assert result.new_line_count < 50

        with open(path) as f:
            new_lines = f.readlines()
        assert count_session_log_entries(new_lines) <= MAX_SESSION_LOG_ENTRIES


class TestCheckDirectory:
    def test_checks_all_files(self, tmp_path):
        _write_memory_file(str(tmp_path / "coder.md"), line_count=40)
        _write_memory_file(str(tmp_path / "social.md"), line_count=40)

        results = check_directory(str(tmp_path))
        assert len(results) == 2
        assert all(r.status == "PASS" for r in results)

    def test_empty_directory(self, tmp_path):
        results = check_directory(str(tmp_path))
        assert results == []

    def test_ignores_non_md(self, tmp_path):
        (tmp_path / "notes.txt").write_text("not a memory file")
        _write_memory_file(str(tmp_path / "coder.md"), line_count=40)

        results = check_directory(str(tmp_path))
        assert len(results) == 1
