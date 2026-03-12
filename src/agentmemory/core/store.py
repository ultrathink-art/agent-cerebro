"""SQLite storage + semantic dedup for long-term memory."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Dict, List, Optional, Any

from agentmemory.core.embeddings import (
    cosine_similarity,
    get_embedding,
    pack_embedding,
    unpack_embedding,
)
from agentmemory.core.schema import get_connection

DEDUP_THRESHOLD = 0.92


class DuplicateError(Exception):
    """Raised when a semantically duplicate entry is detected."""
    pass


class MemoryStore:
    """Store entries in SQLite with semantic dedup."""

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

    def store(
        self,
        role: str,
        category: str,
        text: str,
        tags: Optional[List[str]] = None,
        embed_fn=None,
    ) -> Dict[str, Any]:
        """Store a new entry. Returns entry dict on success.

        Raises DuplicateError if semantically duplicate (cosine > 0.92).
        Falls back to exact text dedup when no API key.
        """
        _validate_inputs(role, category, text)
        tags = tags or []

        if embed_fn is None:
            embed_fn = get_embedding

        embedding = embed_fn(text)

        if embedding is not None:
            rows = self.conn.execute(
                "SELECT id, text, embedding FROM entries WHERE role = ? AND category = ?",
                (role, category),
            ).fetchall()
            for row in rows:
                if row[2] is None:
                    continue
                stored_emb = unpack_embedding(row[2])
                sim = cosine_similarity(embedding, stored_emb)
                if sim > DEDUP_THRESHOLD:
                    raise DuplicateError(row[1])
        else:
            rows = self.conn.execute(
                "SELECT text FROM entries WHERE role = ? AND category = ?",
                (role, category),
            ).fetchall()
            for row in rows:
                if row[0].strip().lower() == text.strip().lower():
                    raise DuplicateError(row[0])

        emb_blob = pack_embedding(embedding) if embedding else None
        tags_json = json.dumps(tags)
        created = date.today().isoformat()

        self.conn.execute(
            "INSERT INTO entries (role, category, text, embedding, tags, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (role, category, text, emb_blob, tags_json, created),
        )
        self.conn.commit()

        return {"text": text, "created_at": created, "tags": tags}

    def count(self, role: str, category: str) -> int:
        """Entry count for a role/category."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM entries WHERE role = ? AND category = ?",
            (role, category),
        ).fetchone()
        return row[0] if row else 0

    def list_categories(self, role: str) -> List[str]:
        """List available categories for a role."""
        rows = self.conn.execute(
            "SELECT DISTINCT category FROM entries WHERE role = ?",
            (role,),
        ).fetchall()
        return sorted(r[0] for r in rows)


def _validate_inputs(role: str, category: str, text: str) -> None:
    if not role or not role.strip():
        raise ValueError("role is required")
    if not category or not category.strip():
        raise ValueError("category is required")
    if not text or not text.strip():
        raise ValueError("text is required")
