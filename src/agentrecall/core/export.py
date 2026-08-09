"""Export memories for a role as markdown or JSON."""
from __future__ import annotations

import json
import sqlite3
from typing import Dict, List, Optional

from agentrecall.core.schema import get_connection


class MemoryExport:
    """Export entries in various formats."""

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

    def export(
        self,
        role: str,
        fmt: str = "md",
        category: Optional[str] = None,
        include_invalidated: bool = False,
    ) -> str:
        """Export entries as markdown or JSON string.

        Args:
            role: Agent role to export.
            fmt: "md" for markdown, "json" for JSON.
            category: Optional category filter.
            include_invalidated: Include lifecycle metadata for audit output.

        Returns:
            Formatted string output.
        """
        entries = self._fetch_entries(role, category, include_invalidated)

        if fmt == "json":
            return self._to_json(entries)
        return self._to_markdown(role, entries, include_invalidated)

    def _fetch_entries(
        self,
        role: str,
        category: Optional[str] = None,
        include_invalidated: bool = False,
    ) -> List[Dict]:
        query = (
            "SELECT id, role, category, text, tags, created_at, "
            "invalidated_at, invalidation_reason, superseded_by "
            "FROM entries WHERE role = ?"
        )
        params: list = [role]

        if not include_invalidated:
            query += " AND invalidated_at IS NULL"

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY category, created_at ASC, id ASC"
        rows = self.conn.execute(query, params).fetchall()

        entries = []
        for row in rows:
            entry = {
                "id": row[0],
                "role": row[1],
                "category": row[2],
                "text": row[3],
                "tags": _parse_tags(row[4]),
                "created_at": row[5],
            }
            if include_invalidated:
                entry.update({
                    "status": "invalidated" if row[6] else "active",
                    "invalidated_at": row[6],
                    "invalidation_reason": row[7],
                    "superseded_by": row[8],
                })
            entries.append(entry)
        return entries

    def _to_markdown(
        self,
        role: str,
        entries: List[Dict],
        include_invalidated: bool = False,
    ) -> str:
        if not entries:
            return f"# {role}\n\nNo entries found.\n"

        lines = [f"# {role}"]
        lines.append("")

        current_category = None
        for entry in entries:
            if entry["category"] != current_category:
                current_category = entry["category"]
                lines.append(f"## {current_category}")
                lines.append("")

            tags_str = ""
            if entry["tags"]:
                tags_str = f" `[{', '.join(entry['tags'])}]`"

            id_str = f" **#{entry['id']}**" if include_invalidated else ""
            audit_str = ""
            if include_invalidated and entry["status"] == "invalidated":
                linkage = ""
                if entry["superseded_by"] is not None:
                    linkage = f"; superseded by #{entry['superseded_by']}"
                audit_str = (
                    f" **[INVALIDATED {entry['invalidated_at']}; "
                    f"reason: {entry['invalidation_reason']}{linkage}]**"
                )

            lines.append(
                f"-{id_str} **{entry['created_at']}**: "
                f"{entry['text']}{tags_str}{audit_str}"
            )

        lines.append("")
        return "\n".join(lines)

    def _to_json(self, entries: List[Dict]) -> str:
        return json.dumps(entries, indent=2)


def _parse_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []
