"""Garbage collection — identify and remove near-duplicate entries."""
from __future__ import annotations

import json
import sqlite3
from typing import Dict, List, Optional, Tuple

from agentrecall.core.embeddings import (
    cosine_similarity,
    unpack_embedding,
)
from agentrecall.core.schema import get_connection
from agentrecall.core.store import DEDUP_THRESHOLD


class MemoryGC:
    """Find and optionally remove near-duplicate entries below dedup threshold."""

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

    def find_duplicates(
        self,
        role: str,
        threshold: Optional[float] = None,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """Find near-duplicate entry pairs.

        Returns list of dicts, each with:
            keep_id, keep_text, remove_id, remove_text, similarity, category
        The older entry (lower id) is kept; newer duplicate is marked for removal.
        """
        thresh = threshold if threshold is not None else DEDUP_THRESHOLD

        query = "SELECT id, category, text, embedding FROM entries WHERE role = ?"
        params: list = [role]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY id ASC"

        rows = self.conn.execute(query, params).fetchall()

        groups: Dict[str, list] = {}
        for row in rows:
            cat = row[1]
            groups.setdefault(cat, []).append(row)

        duplicates = []
        for cat, entries in groups.items():
            dupes = self._find_dupes_in_group(entries, thresh)
            duplicates.extend(dupes)

        return duplicates

    def gc(
        self,
        role: str,
        dry_run: bool = True,
        threshold: Optional[float] = None,
        category: Optional[str] = None,
    ) -> Dict:
        """Run garbage collection.

        Args:
            role: Agent role.
            dry_run: If True, report only. If False, delete duplicates.
            threshold: Cosine similarity threshold (default: DEDUP_THRESHOLD).
            category: Optional category filter.

        Returns:
            Dict with found (count), removed (count), duplicates (list).
        """
        duplicates = self.find_duplicates(role, threshold=threshold, category=category)

        removed = 0
        if not dry_run and duplicates:
            ids_to_remove = [d["remove_id"] for d in duplicates]
            placeholders = ",".join("?" * len(ids_to_remove))
            self.conn.execute(
                f"DELETE FROM entries WHERE id IN ({placeholders})",
                ids_to_remove,
            )
            self.conn.commit()
            removed = len(ids_to_remove)

        return {
            "found": len(duplicates),
            "removed": removed,
            "duplicates": duplicates,
        }

    def _find_dupes_in_group(
        self, entries: list, threshold: float
    ) -> List[Dict]:
        """Find duplicates within a single category group.

        Entries with embeddings are compared via cosine similarity.
        Entries without embeddings are compared via exact text match.
        """
        duplicates = []
        removed_ids: set = set()

        for i, entry_a in enumerate(entries):
            if entry_a[0] in removed_ids:
                continue

            for j in range(i + 1, len(entries)):
                entry_b = entries[j]
                if entry_b[0] in removed_ids:
                    continue

                sim = self._compute_similarity(entry_a, entry_b)
                if sim is not None and sim >= threshold:
                    duplicates.append({
                        "keep_id": entry_a[0],
                        "keep_text": entry_a[2],
                        "remove_id": entry_b[0],
                        "remove_text": entry_b[2],
                        "similarity": round(sim, 4),
                        "category": entry_a[1],
                    })
                    removed_ids.add(entry_b[0])

        return duplicates

    def _compute_similarity(self, a: tuple, b: tuple) -> Optional[float]:
        """Compute similarity between two entries.

        Uses cosine similarity if both have embeddings.
        Uses exact text match (1.0 or 0.0) if either lacks embeddings.
        """
        emb_a = a[3]
        emb_b = b[3]

        if emb_a is not None and emb_b is not None:
            vec_a = unpack_embedding(emb_a)
            vec_b = unpack_embedding(emb_b)
            return cosine_similarity(vec_a, vec_b)

        if a[2].strip().lower() == b[2].strip().lower():
            return 1.0
        return 0.0
