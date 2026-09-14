"""Portable snapshots preserve history and never overwrite user data."""
import os
import sqlite3

import pytest

from agentrecall import backup_database
from agentrecall.cli import main
from agentrecall.core.schema import ensure_schema


def test_backup_preserves_committed_wal_and_all_metadata(tmp_path):
    source = tmp_path / "source.sqlite3"
    conn = sqlite3.connect(source)
    ensure_schema(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.executemany(
        "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(4, "coder", "facts", "old", b"\x01\x02", '["tag"]', "2026-01-01",
          "2026-02-01", "corrected", 7),
         (7, "coder", "facts", "new café", b"\x03\x04", '[]', "2026-02-01",
          None, None, None),
         (9, "qa", "checks", "other role", None, '[]', "2026-03-01",
          None, None, None)],
    )
    conn.commit()
    assert os.path.getsize(str(source) + "-wal") > 0
    # Uncommitted writes must not enter a snapshot.
    conn.execute("UPDATE entries SET text='uncommitted' WHERE id=7")
    target = tmp_path / "portable.sqlite3"
    assert backup_database(str(target), str(source)) == str(target)
    conn.rollback()
    with sqlite3.connect(target) as restored:
        assert restored.execute("SELECT * FROM entries ORDER BY id").fetchall() == (
            conn.execute("SELECT * FROM entries ORDER BY id").fetchall()
        )
        assert restored.execute("SELECT * FROM sqlite_sequence").fetchall() == (
            conn.execute("SELECT * FROM sqlite_sequence").fetchall()
        )
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert restored.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    conn.close()
    assert target.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".cerebro-backup-*"))
    assert not (tmp_path / "portable.sqlite3-wal").exists()


@pytest.mark.parametrize("kind", ["file", "source", "symlink", "dangling", "hardlink"])
def test_destination_is_never_overwritten(tmp_db, tmp_path, kind):
    target = tmp_path / "existing.sqlite3"
    original = open(tmp_db, "rb").read()
    if kind == "source":
        target = tmp_path / "test_memory.sqlite3"
    elif kind == "file":
        target.write_bytes(b"keep me")
    elif kind in ("symlink", "dangling"):
        target.symlink_to(tmp_db if kind == "symlink" else tmp_path / "absent")
    else:
        os.link(tmp_db, target)
    with pytest.raises(FileExistsError):
        backup_database(str(target), tmp_db)
    assert open(tmp_db, "rb").read() == original
    if kind == "file":
        assert target.read_bytes() == b"keep me"


def test_missing_source_is_not_created(tmp_path):
    source, target = tmp_path / "missing", tmp_path / "backup"
    with pytest.raises(sqlite3.OperationalError):
        backup_database(str(target), str(source))
    assert not source.exists()
    assert not target.exists()


@pytest.mark.parametrize("content", [b"not sqlite", b""])
def test_invalid_source_leaves_no_artifact(tmp_path, content):
    source, target = tmp_path / "invalid", tmp_path / "backup"
    source.write_bytes(content)
    with pytest.raises((sqlite3.Error, ValueError)):
        backup_database(str(target), str(source))
    assert source.read_bytes() == content
    assert not target.exists()
    assert not list(tmp_path.glob(".cerebro-backup-*"))


def test_publish_race_preserves_destination_and_cleans_temp(tmp_db, tmp_path, monkeypatch):
    target = tmp_path / "backup"
    real_link = os.link

    def racing_link(source, destination):
        target.write_bytes(b"concurrent writer")
        real_link(source, destination)

    monkeypatch.setattr(os, "link", racing_link)
    with pytest.raises(FileExistsError):
        backup_database(str(target), tmp_db)
    assert target.read_bytes() == b"concurrent writer"
    assert not list(tmp_path.glob(".cerebro-backup-*"))


def test_cli_default_home_and_failure(tmp_db, tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    backup_database(str(home / "memory.sqlite3"), tmp_db)
    monkeypatch.setenv("AGENT_CEREBRO_HOME", str(home))
    target = tmp_path / "backup"
    with pytest.raises(SystemExit) as result:
        main(["backup", str(target)])
    assert result.value.code == 0
    assert "Backup saved:" in capsys.readouterr().out
    with pytest.raises(SystemExit) as result:
        main(["backup", str(target), "--db", tmp_db])
    assert result.value.code == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "already exists" in captured.err


def test_pre_lifecycle_database_is_copied_without_migration(tmp_path):
    source, target = tmp_path / "legacy", tmp_path / "backup"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, text TEXT)")
        conn.execute("INSERT INTO entries VALUES (42, 'legacy')")
    before = source.read_bytes()
    backup_database(str(target), str(source))
    assert source.read_bytes() == before
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT * FROM entries").fetchall() == [(42, "legacy")]


def test_missing_destination_directory_fails_without_creating_it(tmp_db, tmp_path):
    target = tmp_path / "missing" / "backup"
    with pytest.raises(FileNotFoundError):
        backup_database(str(target), tmp_db)
    assert not target.parent.exists()
