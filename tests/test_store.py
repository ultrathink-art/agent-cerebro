"""Tests for MemoryStore."""
import math
from datetime import date

import pytest

from agentrecall.core.store import MemoryStore, DuplicateError
from conftest import fake_embedding, make_embed_fn, null_embed_fn


class TestStore:
    @pytest.mark.parametrize("existing_embed", [null_embed_fn, make_embed_fn(0.1)])
    @pytest.mark.parametrize("next_embed", [null_embed_fn, make_embed_fn(0.5)])
    def test_exact_duplicate_is_rejected_across_embedding_availability(
        self, tmp_db, existing_embed, next_embed
    ):
        store = MemoryStore(db_path=tmp_db)
        original = store.store(
            "coder", "gotchas", "  Preserve outage memories  ",
            tags=["original"], embed_fn=existing_embed,
        )
        before = store.conn.execute("SELECT * FROM entries").fetchall()
        calls = []

        def embed(text):
            calls.append(text)
            return next_embed(text)

        with pytest.raises(DuplicateError, match="Preserve outage memories"):
            store.store(
                "coder", "gotchas", "preserve OUTAGE memories",
                tags=["retry"], embed_fn=embed,
            )

        assert calls == []  # A known duplicate needs no provider request.
        assert store.conn.execute("SELECT * FROM entries").fetchall() == before
        assert store.count(original["role"], original["category"]) == 1
        store.close()

    def test_outage_recovery_allows_distinct_text_and_other_scopes(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("coder", "gotchas", "outage memory", embed_fn=null_embed_fn)
        for role, category, text in [
            ("coder", "gotchas", "distinct memory"),
            ("qa", "gotchas", "outage memory"),
            ("coder", "learnings", "outage memory"),
        ]:
            store.store(role, category, text, embed_fn=make_embed_fn(0.1))
        assert store.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 4
        store.close()

    def test_store_creates_entry(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        entry = store.store(
            "test_role", "test_cat", "my test entry",
            tags=["a", "b"],
            embed_fn=make_embed_fn(0.1),
        )

        assert entry["text"] == "my test entry"
        assert entry["created_at"] == date.today().isoformat()
        assert entry["tags"] == ["a", "b"]
        assert store.count("test_role", "test_cat") == 1
        store.close()

    def test_store_appends_entries(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "first", embed_fn=make_embed_fn(0.1))
        store.store("r", "c", "second", embed_fn=make_embed_fn(0.5))

        assert store.count("r", "c") == 2
        store.close()

    def test_store_detects_semantic_duplicates(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        emb_fn = make_embed_fn(0.1)
        store.store("r", "c", "deploy order loss", embed_fn=emb_fn)

        with pytest.raises(DuplicateError):
            store.store("r", "c", "rapid deploys lost orders", embed_fn=emb_fn)
        store.close()

    def test_store_allows_different_embeddings(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", embed_fn=make_embed_fn(0.1))
        store.store("r", "c", "sticker design guidelines", embed_fn=make_embed_fn(5.0))

        assert store.count("r", "c") == 2
        store.close()

    def test_store_without_api_key_exact_dedup(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", embed_fn=null_embed_fn)

        with pytest.raises(DuplicateError):
            store.store("r", "c", "deploy order loss", embed_fn=null_embed_fn)
        store.close()

    def test_store_without_api_key_case_insensitive_dedup(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "Deploy Order Loss", embed_fn=null_embed_fn)

        with pytest.raises(DuplicateError):
            store.store("r", "c", "deploy order loss", embed_fn=null_embed_fn)
        store.close()

    def test_store_without_api_key_allows_different_text(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", embed_fn=null_embed_fn)
        store.store("r", "c", "sticker design", embed_fn=null_embed_fn)

        assert store.count("r", "c") == 2
        store.close()

    def test_store_rejects_blank_role(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        with pytest.raises(ValueError):
            store.store("", "c", "text", embed_fn=null_embed_fn)
        store.close()

    def test_store_rejects_blank_category(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        with pytest.raises(ValueError):
            store.store("r", "", "text", embed_fn=null_embed_fn)
        store.close()

    def test_store_rejects_blank_text(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        with pytest.raises(ValueError):
            store.store("r", "c", "", embed_fn=null_embed_fn)
        store.close()

    def test_store_rejects_whitespace_only_text(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        with pytest.raises(ValueError):
            store.store("r", "c", "   ", embed_fn=null_embed_fn)
        store.close()

    def test_store_tags_default_empty(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        entry = store.store("r", "c", "text", embed_fn=null_embed_fn)

        assert entry["tags"] == []
        store.close()


class TestCount:
    def test_count_zero_for_empty(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        assert store.count("r", "empty") == 0
        store.close()

    def test_count_correct(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "one", embed_fn=make_embed_fn(0.1))
        store.store("r", "c", "two", embed_fn=make_embed_fn(0.5))

        assert store.count("r", "c") == 2
        store.close()


class TestListCategories:
    def test_empty_for_missing_role(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        assert store.list_categories("ghost") == []
        store.close()

    def test_returns_sorted_categories(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("social", "exhausted_stories", "entry1", embed_fn=make_embed_fn(0.1))
        store.store("social", "rejected_topics", "entry2", embed_fn=make_embed_fn(0.2))

        cats = store.list_categories("social")
        assert cats == ["exhausted_stories", "rejected_topics"]
        store.close()

    def test_categories_scoped_to_role(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("social", "stories", "e1", embed_fn=make_embed_fn(0.1))
        store.store("coder", "gotchas", "e2", embed_fn=make_embed_fn(0.2))

        assert store.list_categories("social") == ["stories"]
        assert store.list_categories("coder") == ["gotchas"]
        store.close()
