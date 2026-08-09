"""Explicit lifecycle operations for correcting stale long-term memories."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agentrecall.core.schema import get_connection
from agentrecall.core.store import MemoryStore


class EntryNotFoundError(Exception):
    """Raised when a lifecycle target does not exist."""


class AlreadyInvalidatedError(Exception):
    """Raised when a lifecycle target is no longer active."""


class MemoryLifecycle:
    """Soft-invalidate and atomically supersede long-term memories."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def invalidate(self, entry_id: int, reason: str) -> Dict[str, Any]:
        """Soft-invalidate one active entry while preserving its history."""
        if not reason or not reason.strip():
            raise ValueError("reason is required")

        target = self._target(entry_id)
        invalidated_at = _utc_timestamp()
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE entries "
                "SET invalidated_at = ?, invalidation_reason = ? "
                "WHERE id = ? AND invalidated_at IS NULL",
                (invalidated_at, reason.strip(), entry_id),
            )
            if cursor.rowcount != 1:
                raise AlreadyInvalidatedError(
                    f"Entry #{entry_id} is already invalidated"
                )

        return {
            "id": target["id"],
            "invalidated_at": invalidated_at,
            "invalidation_reason": reason.strip(),
            "superseded_by": None,
        }

    def supersede(
        self,
        entry_id: int,
        replacement_text: str,
        tags: Optional[List[str]] = None,
        reason: Optional[str] = None,
        embed_fn=None,
    ) -> Dict[str, Any]:
        """Atomically replace one belief and link the old record to the new one."""
        target = self._target(entry_id)
        replacement_tags = target["tags"] if tags is None else tags
        invalidation_reason = (
            reason.strip()
            if reason and reason.strip()
            else "Superseded by corrected memory"
        )
        invalidated_at = _utc_timestamp()
        store = MemoryStore(connection=self.conn)

        with self.conn:
            replacement = store.store(
                target["role"],
                target["category"],
                replacement_text,
                tags=replacement_tags,
                embed_fn=embed_fn,
                _exclude_entry_id=entry_id,
                _commit=False,
            )
            cursor = self.conn.execute(
                "UPDATE entries "
                "SET invalidated_at = ?, invalidation_reason = ?, superseded_by = ? "
                "WHERE id = ? AND invalidated_at IS NULL",
                (
                    invalidated_at,
                    invalidation_reason,
                    replacement["id"],
                    entry_id,
                ),
            )
            if cursor.rowcount != 1:
                raise AlreadyInvalidatedError(
                    f"Entry #{entry_id} is already invalidated"
                )

        return {
            "old_id": entry_id,
            "new_id": replacement["id"],
            "replacement": replacement,
        }

    def _target(self, entry_id: int) -> Dict[str, Any]:
        row = self.conn.execute(
            "SELECT id, role, category, text, tags, invalidated_at "
            "FROM entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if row is None:
            raise EntryNotFoundError(f"Entry #{entry_id} not found")
        if row[5] is not None:
            raise AlreadyInvalidatedError(
                f"Entry #{entry_id} is already invalidated"
            )
        return {
            "id": row[0],
            "role": row[1],
            "category": row[2],
            "text": row[3],
            "tags": _parse_tags(row[4]),
        }


def _parse_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
