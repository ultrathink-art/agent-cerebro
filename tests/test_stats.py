"""Tests for MemoryStats."""
import json
import sqlite3
from datetime import date

import pytest

from agentrecall.core.stats import MemoryStats
from agentrecall.core.schema import ensure_schema
from agentrecall.core.embeddings import pack_embedding
from conftest import fake_embedding


def _insert_entry(db_path, role, category, text, with_embedding=False, created_at=None):
    conn = sqlite3.connect(db_path)
    ensure_schema(conn)
    created = created_at or date.today().isoformat()
    emb = pack_embedding(fake_embedding(0.1)) if with_embedding else None
    conn.execute(
        "INSERT INTO entries (role, category, text, embedding, tags, created_at) "
        "VALUES (?, ?, ?, ?, '[]', ?)",
        (role, category, text, emb, created),
    )
    conn.commit()
    conn.close()


class TestStats:
    def test_empty_db(self, tmp_db):
        ms = MemoryStats(db_path=tmp_db)
        s = ms.stats()
        assert s["total_entries"] == 0
        assert s["total_with_embeddings"] == 0
        assert s["embedding_coverage_pct"] == 0.0
        assert s["categories"] == []
        assert s["oldest_entry"] is None
        ms.close()

    def test_counts_entries(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry1", with_embedding=True)
        _insert_entry(tmp_db, "coder", "gotchas", "entry2", with_embedding=False)
        _insert_entry(tmp_db, "social", "stories", "entry3", with_embedding=True)

        ms = MemoryStats(db_path=tmp_db)
        s = ms.stats()
        assert s["total_entries"] == 3
        assert s["total_with_embeddings"] == 2
        assert s["embedding_coverage_pct"] == 66.7
        ms.close()

    def test_role_filter(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry1")
        _insert_entry(tmp_db, "social", "stories", "entry2")

        ms = MemoryStats(db_path=tmp_db)
        s = ms.stats(role="coder")
        assert s["total_entries"] == 1
        ms.close()

    def test_categories_breakdown(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "e1", with_embedding=True)
        _insert_entry(tmp_db, "coder", "gotchas", "e2", with_embedding=True)
        _insert_entry(tmp_db, "coder", "fix_attempts", "e3", with_embedding=False)

        ms = MemoryStats(db_path=tmp_db)
        s = ms.stats(role="coder")
        assert len(s["categories"]) == 2

        gotchas = next(c for c in s["categories"] if c["category"] == "gotchas")
        assert gotchas["count"] == 2
        assert gotchas["with_embeddings"] == 2

        fixes = next(c for c in s["categories"] if c["category"] == "fix_attempts")
        assert fixes["count"] == 1
        assert fixes["with_embeddings"] == 0
        ms.close()

    def test_date_range(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "old", created_at="2026-01-01")
        _insert_entry(tmp_db, "coder", "gotchas", "new", created_at="2026-03-15")

        ms = MemoryStats(db_path=tmp_db)
        s = ms.stats()
        assert s["oldest_entry"] == "2026-01-01"
        assert s["newest_entry"] == "2026-03-15"
        ms.close()

    def test_roles_list(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "e1")
        _insert_entry(tmp_db, "social", "stories", "e2")
        _insert_entry(tmp_db, "designer", "rejected", "e3")

        ms = MemoryStats(db_path=tmp_db)
        s = ms.stats()
        assert s["roles"] == ["coder", "designer", "social"]
        ms.close()

    def test_db_size_nonzero(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry1")

        ms = MemoryStats(db_path=tmp_db)
        s = ms.stats()
        assert s["db_size_bytes"] > 0
        ms.close()
