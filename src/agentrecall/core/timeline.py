"""Chronological timeline view of memories."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from agentrecall.core.schema import get_connection


class MemoryTimeline:
    """Query entries in chronological order with optional time filtering."""

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

    def timeline(
        self,
        role: str,
        last: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Return entries in reverse chronological order.

        Args:
            role: Agent role to filter by.
            last: Duration string like "7d", "30d", "2w". None = all.
            category: Optional category filter.
            limit: Max entries to return.

        Returns:
            List of dicts with id, role, category, text, tags, created_at.
        """
        query = "SELECT id, role, category, text, tags, created_at FROM entries WHERE role = ?"
        params: list = [role]

        if category:
            query += " AND category = ?"
            params.append(category)

        if last:
            cutoff = _parse_duration(last)
            if cutoff:
                query += " AND created_at >= ?"
                params.append(cutoff.isoformat())

        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()

        return [
            {
                "id": r[0],
                "role": r[1],
                "category": r[2],
                "text": r[3],
                "tags": _parse_tags(r[4]),
                "created_at": r[5],
            }
            for r in rows
        ]


def _parse_duration(duration_str: str) -> Optional[date]:
    """Parse a duration string (7d, 2w, 3m) into a cutoff date."""
    m = re.match(r"^(\d+)([dwm])$", duration_str.strip().lower())
    if not m:
        return None

    amount = int(m.group(1))
    unit = m.group(2)

    today = date.today()
    if unit == "d":
        return today - timedelta(days=amount)
    elif unit == "w":
        return today - timedelta(weeks=amount)
    elif unit == "m":
        return today - timedelta(days=amount * 30)
    return None


def _parse_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []
