"""Semantic search + keyword fallback for long-term memory."""
from __future__ import annotations

import json
import re
import sys
from typing import Dict, List, Optional, Any

from agentrecall.core.embeddings import (
    cosine_similarity,
    get_embedding,
    unpack_embedding,
)
from agentrecall.core.schema import get_connection

SEARCH_THRESHOLD = 0.75


class MemorySearch:
    """Search entries using embeddings + keyword fallback."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._conn = None

    @property
    def conn(self):
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

    def search(
        self,
        role: str,
        category: str,
        query: str,
        embed_fn=None,
        tag: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Search entries semantically. Returns list of matching texts.

        Args:
            role: Agent role.
            category: Category to search.
            query: Search query text.
            embed_fn: Optional embedding function override.
            tag: Optional tag filter — only return entries containing this tag.
            limit: Optional max number of results (top-N by relevance).
        """
        rows = self.conn.execute(
            "SELECT text, embedding, tags FROM entries WHERE role = ? AND category = ?",
            (role, category),
        ).fetchall()

        if tag:
            rows = [r for r in rows if tag in _parse_tags(r[2])]

        if not rows:
            return []

        if embed_fn is None:
            embed_fn = get_embedding

        query_embedding = embed_fn(query)

        if query_embedding is None:
            # No API key OR embeddings degraded after retries — keyword search.
            print(
                "WARNING: embeddings unavailable — using keyword search",
                file=sys.stderr,
            )
            entries = [
                {"text": r[0], "tags": _parse_tags(r[2])} for r in rows
            ]
            return _apply_limit(keyword_fallback(entries, query), limit)

        scored = []
        for row in rows:
            if row[1] is None:
                continue
            stored_emb = unpack_embedding(row[1])
            sim = cosine_similarity(query_embedding, stored_emb)
            if sim > SEARCH_THRESHOLD:
                scored.append((row[0], sim))

        results = [text for text, _ in sorted(scored, key=lambda x: -x[1])]

        if not results:
            entries = [
                {"text": r[0], "tags": _parse_tags(r[2])} for r in rows
            ]
            return _apply_limit(keyword_fallback(entries, query), limit)

        return _apply_limit(results, limit)

    def count(self, role: str, category: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM entries WHERE role = ? AND category = ?",
            (role, category),
        ).fetchone()
        return row[0] if row else 0


def keyword_fallback(entries: List[Dict[str, Any]], query: str) -> List[str]:
    """Keyword fallback when embeddings unavailable.

    Requires >= 50% of query keywords to match (min 1).
    """
    keywords = [w for w in re.split(r"[\s\-_,]+", query.lower()) if len(w) >= 3]
    if not keywords:
        return []

    threshold = max(len(keywords) // 2 + (len(keywords) % 2), 1)
    results = []

    for entry in entries:
        text = (entry["text"] + " " + " ".join(entry.get("tags", []))).lower()
        matches = sum(1 for kw in keywords if kw in text)
        if matches >= threshold:
            results.append(entry["text"])

    return results


def keyword_prefilter(entries: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Narrow candidates before embedding search."""
    keywords = [w for w in re.split(r"[\s\-_,]+", query.lower()) if len(w) >= 3]
    if not keywords:
        return entries

    return [
        e for e in entries
        if any(
            kw in (e["text"] + " " + " ".join(e.get("tags", []))).lower()
            for kw in keywords
        )
    ]


def _apply_limit(results: List[str], limit: Optional[int]) -> List[str]:
    """Cap result count to top-N. Non-positive/None limit = no cap."""
    if limit is not None and limit > 0:
        return results[:limit]
    return results


def _parse_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []
