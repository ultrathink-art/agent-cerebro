"""Storage metrics and statistics for memory DB."""
from __future__ import annotations

import os
import sqlite3
from typing import Dict, List, Optional, Any

from agentrecall.core.schema import get_connection


class MemoryStats:
    """Compute storage metrics, embedding coverage, category breakdown."""

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

    def stats(self, role: Optional[str] = None) -> Dict[str, Any]:
        """Compute stats for a role (or all roles if None).

        Returns dict with:
            total_entries, total_with_embeddings, embedding_coverage_pct,
            db_size_bytes, roles (list), categories (list of dicts),
            oldest_entry, newest_entry
        """
        db_path = self.db_path or self._resolve_db_path()
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        where = ""
        params: list = []
        if role:
            where = "WHERE role = ?"
            params = [role]

        total = self.conn.execute(
            f"SELECT COUNT(*) FROM entries {where}", params
        ).fetchone()[0]

        with_emb = self.conn.execute(
            f"SELECT COUNT(*) FROM entries {where}"
            + (" AND" if where else "WHERE")
            + " embedding IS NOT NULL",
            params,
        ).fetchone()[0]

        coverage = round(100 * with_emb / total, 1) if total > 0 else 0.0

        roles = [
            r[0]
            for r in self.conn.execute(
                "SELECT DISTINCT role FROM entries ORDER BY role"
            ).fetchall()
        ]

        cat_query = (
            "SELECT role, category, COUNT(*) as cnt, "
            "SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_emb "
            f"FROM entries {where} GROUP BY role, category ORDER BY role, category"
        )
        cat_rows = self.conn.execute(cat_query, params).fetchall()

        categories = [
            {
                "role": r[0],
                "category": r[1],
                "count": r[2],
                "with_embeddings": r[3],
            }
            for r in cat_rows
        ]

        date_range = self.conn.execute(
            f"SELECT MIN(created_at), MAX(created_at) FROM entries {where}",
            params,
        ).fetchone()
        oldest = date_range[0] if date_range else None
        newest = date_range[1] if date_range else None

        return {
            "total_entries": total,
            "total_with_embeddings": with_emb,
            "embedding_coverage_pct": coverage,
            "db_size_bytes": db_size,
            "roles": roles,
            "categories": categories,
            "oldest_entry": oldest,
            "newest_entry": newest,
        }

    def _resolve_db_path(self) -> str:
        from agentrecall.core.schema import get_db_path
        return get_db_path()
