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
        records = self.search_records(
            role,
            category,
            query,
            embed_fn=embed_fn,
            tag=tag,
            limit=limit,
        )
        return [record["text"] for record in records]

    def search_records(
        self,
        role: str,
        category: str,
        query: str,
        embed_fn=None,
        tag: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search active entries and return addressable record dictionaries."""
        rows = self.conn.execute(
            "SELECT id, role, category, text, embedding, tags, created_at "
            "FROM entries WHERE role = ? AND category = ? "
            "AND invalidated_at IS NULL",
            (role, category),
        ).fetchall()

        records = [
            {
                "id": row[0],
                "role": row[1],
                "category": row[2],
                "text": row[3],
                "embedding": row[4],
                "tags": _parse_tags(row[5]),
                "created_at": row[6],
            }
            for row in rows
        ]

        if tag:
            records = [record for record in records if tag in record["tags"]]

        if not records:
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
            return _public_records(
                _apply_limit(keyword_fallback_records(records, query), limit)
            )

        scored = []
        for record in records:
            if record["embedding"] is None:
                continue
            stored_emb = unpack_embedding(record["embedding"])
            sim = cosine_similarity(query_embedding, stored_emb)
            if sim > SEARCH_THRESHOLD:
                scored.append((record, sim))

        results = [
            record for record, _ in sorted(scored, key=lambda item: -item[1])
        ]

        if not results:
            return _public_records(
                _apply_limit(keyword_fallback_records(records, query), limit)
            )

        return _public_records(_apply_limit(results, limit))

    def count(self, role: str, category: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM entries "
            "WHERE role = ? AND category = ? AND invalidated_at IS NULL",
            (role, category),
        ).fetchone()
        return row[0] if row else 0


def keyword_fallback(entries: List[Dict[str, Any]], query: str) -> List[str]:
    """Keyword fallback when embeddings unavailable.

    Requires >= 50% of query keywords to match (min 1).
    """
    return [entry["text"] for entry in keyword_fallback_records(entries, query)]


def keyword_fallback_records(
    entries: List[Dict[str, Any]], query: str
) -> List[Dict[str, Any]]:
    """Keyword fallback that preserves record metadata such as stable IDs."""
    keywords = [
        word
        for word in re.split(r"[\s\-_,]+", query.lower())
        if len(word) >= 3
    ]
    if not keywords:
        return []

    threshold = max(len(keywords) // 2 + (len(keywords) % 2), 1)
    results = []
    for entry in entries:
        text = (entry["text"] + " " + " ".join(entry.get("tags", []))).lower()
        matches = sum(1 for keyword in keywords if keyword in text)
        if matches >= threshold:
            results.append(entry)
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


def _apply_limit(results: List[Any], limit: Optional[int]) -> List[Any]:
    """Cap result count to top-N. Non-positive/None limit = no cap."""
    if limit is not None and limit > 0:
        return results[:limit]
    return results


def _public_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove internal embedding blobs from public search records."""
    return [
        {key: value for key, value in record.items() if key != "embedding"}
        for record in records
    ]


def _parse_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []
