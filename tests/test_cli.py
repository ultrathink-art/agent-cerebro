"""Tests for CLI integration."""
import os
import subprocess
import sys

import pytest

from agentmemory.cli import main
from agentmemory.core.store import MemoryStore
from tests.conftest import make_embed_fn, null_embed_fn


class TestCLIHelp:
    def test_main_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_store_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["store", "--help"])
        assert exc_info.value.code == 0

    def test_search_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["search", "--help"])
        assert exc_info.value.code == 0

    def test_list_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["list", "--help"])
        assert exc_info.value.code == 0

    def test_check_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["check", "--help"])
        assert exc_info.value.code == 0

    def test_init_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["init", "--help"])
        assert exc_info.value.code == 0

    def test_migrate_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["migrate", "--help"])
        assert exc_info.value.code == 0

    def test_no_command_shows_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 0


class TestCLIStoreSearch:
    def test_store_and_search_roundtrip(self, tmp_db, monkeypatch):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["store", "test", "cat", "deploy order loss", "--db", tmp_db])
        assert exc_info.value.code == 0

        with pytest.raises(SystemExit) as exc_info:
            main(["search", "test", "cat", "deploy order", "--db", tmp_db])
        assert exc_info.value.code == 0

    def test_store_duplicate_exits_1(self, tmp_db, monkeypatch):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["store", "test", "cat", "same text", "--db", tmp_db])
        assert exc_info.value.code == 0

        with pytest.raises(SystemExit) as exc_info:
            main(["store", "test", "cat", "same text", "--db", tmp_db])
        assert exc_info.value.code == 1

    def test_search_no_results_exits_1(self, tmp_db, monkeypatch):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["search", "test", "cat", "nothing here", "--db", tmp_db])
        assert exc_info.value.code == 1


class TestCLIList:
    def test_list_empty(self, tmp_db):
        with pytest.raises(SystemExit) as exc_info:
            main(["list", "ghost", "--db", tmp_db])
        assert exc_info.value.code == 0

    def test_list_with_entries(self, tmp_db, monkeypatch):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["store", "social", "stories", "entry1", "--db", tmp_db])
        assert exc_info.value.code == 0

        with pytest.raises(SystemExit) as exc_info:
            main(["list", "social", "--db", tmp_db])
        assert exc_info.value.code == 0


class TestCLIInit:
    def test_init_creates_directory(self, tmp_path):
        target = str(tmp_path / "new_memory")
        with pytest.raises(SystemExit) as exc_info:
            main(["init", "--dir", target])
        assert exc_info.value.code == 0
        assert os.path.exists(target)
        assert os.path.exists(os.path.join(target, "memory.sqlite3"))


class TestCLICheck:
    def test_check_empty_dir(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            main(["check", "--dir", str(tmp_path)])
        assert exc_info.value.code == 0

    def test_check_long_term_missing_db(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            main([
                "check", "--long-term",
                "--db", str(tmp_path / "nonexistent.sqlite3"),
            ])
        assert exc_info.value.code == 1
