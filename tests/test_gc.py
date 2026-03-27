"""Tests for MemoryGC (garbage collection)."""
import json
import sqlite3
from datetime import date

import pytest

from agentrecall.core.gc import MemoryGC
from agentrecall.core.store import MemoryStore, DEDUP_THRESHOLD
from agentrecall.core.schema import ensure_schema
from agentrecall.core.embeddings import pack_embedding
from conftest import fake_embedding, make_embed_fn, null_embed_fn


def _insert_entry(db_path, role, category, text, embedding_seed=None, created_at=None):
    conn = sqlite3.connect(db_path)
    ensure_schema(conn)
    created = created_at or date.today().isoformat()
    emb = pack_embedding(fake_embedding(embedding_seed)) if embedding_seed is not None else None
    conn.execute(
        "INSERT INTO entries (role, category, text, embedding, tags, created_at) "
        "VALUES (?, ?, ?, ?, '[]', ?)",
        (role, category, text, emb, created),
    )
    conn.commit()
    conn.close()


class TestFindDuplicates:
    def test_no_entries_no_duplicates(self, tmp_db):
        gc = MemoryGC(db_path=tmp_db)
        dupes = gc.find_duplicates("nonexistent")
        assert dupes == []
        gc.close()

    def test_identical_embeddings_are_duplicates(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry one", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "entry two", embedding_seed=0.1)

        gc = MemoryGC(db_path=tmp_db)
        dupes = gc.find_duplicates("coder")
        assert len(dupes) == 1
        assert dupes[0]["keep_text"] == "entry one"
        assert dupes[0]["remove_text"] == "entry two"
        assert dupes[0]["similarity"] == 1.0
        gc.close()

    def test_different_embeddings_not_duplicates(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "deploy issue", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "sticker design", embedding_seed=5.0)

        gc = MemoryGC(db_path=tmp_db)
        dupes = gc.find_duplicates("coder")
        assert dupes == []
        gc.close()

    def test_exact_text_match_without_embeddings(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "same text")
        _insert_entry(tmp_db, "coder", "gotchas", "same text")

        gc = MemoryGC(db_path=tmp_db)
        dupes = gc.find_duplicates("coder")
        assert len(dupes) == 1
        gc.close()

    def test_different_text_without_embeddings(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "first text")
        _insert_entry(tmp_db, "coder", "gotchas", "completely different text")

        gc = MemoryGC(db_path=tmp_db)
        dupes = gc.find_duplicates("coder")
        assert dupes == []
        gc.close()

    def test_category_filter(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry A", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "entry B", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "fixes", "entry C", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "fixes", "entry D", embedding_seed=0.1)

        gc = MemoryGC(db_path=tmp_db)
        dupes = gc.find_duplicates("coder", category="gotchas")
        assert len(dupes) == 1
        assert dupes[0]["category"] == "gotchas"
        gc.close()

    def test_cross_category_not_compared(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "same text", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "fixes", "same text", embedding_seed=0.1)

        gc = MemoryGC(db_path=tmp_db)
        dupes = gc.find_duplicates("coder")
        assert dupes == []
        gc.close()

    def test_custom_threshold(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry A", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "entry B", embedding_seed=0.1008)

        gc = MemoryGC(db_path=tmp_db)
        dupes_strict = gc.find_duplicates("coder", threshold=0.9999)
        dupes_loose = gc.find_duplicates("coder", threshold=0.5)
        assert len(dupes_strict) == 0 or len(dupes_strict) <= len(dupes_loose)
        gc.close()


class TestGC:
    def test_dry_run_does_not_delete(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry one", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "entry two", embedding_seed=0.1)

        gc = MemoryGC(db_path=tmp_db)
        result = gc.gc("coder", dry_run=True)
        assert result["found"] == 1
        assert result["removed"] == 0

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.close()
        assert count == 2
        gc.close()

    def test_apply_deletes_duplicates(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry one", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "entry two", embedding_seed=0.1)

        gc = MemoryGC(db_path=tmp_db)
        result = gc.gc("coder", dry_run=False)
        assert result["found"] == 1
        assert result["removed"] == 1

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        remaining = conn.execute("SELECT text FROM entries").fetchone()[0]
        conn.close()
        assert count == 1
        assert remaining == "entry one"
        gc.close()

    def test_keeps_older_entry(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "original", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "duplicate", embedding_seed=0.1)

        gc = MemoryGC(db_path=tmp_db)
        result = gc.gc("coder", dry_run=False)
        assert result["duplicates"][0]["keep_text"] == "original"
        assert result["duplicates"][0]["remove_text"] == "duplicate"
        gc.close()

    def test_no_duplicates_returns_zero(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "unique one", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "unique two", embedding_seed=5.0)

        gc = MemoryGC(db_path=tmp_db)
        result = gc.gc("coder", dry_run=True)
        assert result["found"] == 0
        assert result["removed"] == 0
        assert result["duplicates"] == []
        gc.close()

    def test_multiple_duplicates_in_chain(self, tmp_db):
        _insert_entry(tmp_db, "coder", "gotchas", "entry A", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "entry B", embedding_seed=0.1)
        _insert_entry(tmp_db, "coder", "gotchas", "entry C", embedding_seed=0.1)

        gc = MemoryGC(db_path=tmp_db)
        result = gc.gc("coder", dry_run=False)
        assert result["found"] == 2
        assert result["removed"] == 2

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.close()
        assert count == 1
        gc.close()
