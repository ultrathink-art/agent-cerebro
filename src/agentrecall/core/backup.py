"""Lossless, offline snapshots of the long-term memory database."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Optional

from agentrecall.core.schema import get_db_path


def backup_database(destination: str, db_path: Optional[str] = None) -> str:
    """Copy all long-term memory to a new, owner-readable SQLite file.

    Uses SQLite's online backup API so committed WAL data is included. The
    source is opened read-only without schema migration; a missing source is an
    error. Publication is atomic and never replaces an existing destination,
    including symlinks. Short-term markdown files are not part of this snapshot.
    """
    source_path = Path(db_path or get_db_path()).absolute()
    target = Path(destination).absolute()
    if os.path.lexists(target):
        raise FileExistsError(f"Backup destination already exists: {target}")

    # URI mode=ro prevents SQLite from silently creating an empty source DB.
    source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    temporary = None
    try:
        if source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone() is None:
            raise ValueError("Source is not a Cerebro memory database (no entries table)")
        fd, temporary = tempfile.mkstemp(prefix=".cerebro-backup-", dir=target.parent)
        os.close(fd)  # mkstemp creates mode 0600, independent of the process umask.
        snapshot = sqlite3.connect(temporary)
        try:
            source.backup(snapshot)
            # A WAL-mode source must become a standalone portable database.
            snapshot.execute("PRAGMA journal_mode=DELETE")
            if snapshot.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("Backup failed SQLite integrity check")
        finally:
            snapshot.close()
        with open(temporary, "rb") as handle:
            os.fsync(handle.fileno())
        # Unlike rename/replace, link fails if another writer created target.
        os.link(temporary, target)
        return str(target)
    finally:
        source.close()
        if temporary is not None:
            for suffix in ("", "-journal", "-wal", "-shm"):
                try:
                    os.unlink(temporary + suffix)
                except FileNotFoundError:
                    pass
