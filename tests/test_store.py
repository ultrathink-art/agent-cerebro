"""Tests for MemoryStore."""
import math
from datetime import date

import pytest

from agentmemory.core.store import MemoryStore, DuplicateError
from tests.conftest import fake_embedding, make_embed_fn, null_embed_fn


class TestStore:
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
