"""Tests for MemorySearch and keyword fallback."""
import math

import pytest

from agentmemory.core.search import MemorySearch, keyword_fallback, keyword_prefilter
from agentmemory.core.store import MemoryStore
from tests.conftest import fake_embedding, make_embed_fn, null_embed_fn


class TestSearch:
    def test_search_empty_category(self, tmp_db):
        search = MemorySearch(db_path=tmp_db)
        result = search.search("nonexistent", "cat", "query", embed_fn=make_embed_fn())
        assert result == []
        search.close()

    def test_search_returns_matches_by_similarity(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", embed_fn=make_embed_fn(0.1))
        store.store("r", "c", "sticker design rejected", embed_fn=make_embed_fn(5.0))
        # Similar to 0.1 but below dedup threshold
        store.store("r", "c", "rapid deploys sqlite wal", embed_fn=make_embed_fn(0.1008))
        store.close()

        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy caused orders to vanish", embed_fn=make_embed_fn(0.1))

        assert "deploy order loss" in result
        assert "rapid deploys sqlite wal" in result
        assert "sticker design rejected" not in result
        search.close()

    def test_search_keyword_fallback_no_api_key(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", embed_fn=null_embed_fn)
        store.store("r", "c", "sticker design rejected", embed_fn=null_embed_fn)
        store.close()

        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy order", embed_fn=null_embed_fn)

        assert len(result) == 1
        assert "deploy order loss" in result
        search.close()

    def test_search_falls_back_when_no_embedding_matches(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", embed_fn=make_embed_fn(0.1))
        store.close()

        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy order", embed_fn=make_embed_fn(99.0))

        assert len(result) == 1
        assert "deploy order loss" in result
        search.close()

    def test_search_returns_empty_when_no_keyword_match(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "sticker design rejected", embed_fn=null_embed_fn)
        store.close()

        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy order", embed_fn=null_embed_fn)
        assert result == []
        search.close()


class TestKeywordFallback:
    def test_requires_half_keywords(self):
        entries = [
            {"text": "deploy order loss sqlite wal", "tags": []},
            {"text": "sticker design rejected", "tags": []},
        ]
        result = keyword_fallback(entries, "deploy orders sqlite")
        assert len(result) == 1
        assert result[0] == "deploy order loss sqlite wal"

    def test_empty_query_returns_empty(self):
        entries = [{"text": "anything", "tags": []}]
        assert keyword_fallback(entries, "") == []

    def test_short_words_ignored(self):
        entries = [{"text": "deploy to server", "tags": []}]
        result = keyword_fallback(entries, "to a")
        assert result == []

    def test_tags_included_in_search(self):
        entries = [
            {"text": "some text", "tags": ["deploy", "orders"]},
        ]
        result = keyword_fallback(entries, "deploy orders")
        assert len(result) == 1

    def test_single_keyword_needs_one_match(self):
        entries = [{"text": "deploy order loss", "tags": []}]
        result = keyword_fallback(entries, "deploy")
        assert len(result) == 1


class TestKeywordPrefilter:
    def test_filters_by_keywords(self):
        entries = [
            {"text": "deploy order loss", "tags": []},
            {"text": "sticker design", "tags": []},
            {"text": "rapid deploy sqlite", "tags": ["deploy"]},
        ]
        filtered = keyword_prefilter(entries, "deploy orders")
        assert len(filtered) == 2
        assert filtered[0]["text"] == "deploy order loss"

    def test_empty_query_returns_all(self):
        entries = [{"text": "anything", "tags": []}]
        assert keyword_prefilter(entries, "") == entries

    def test_no_matches_returns_empty(self):
        entries = [{"text": "sticker design", "tags": []}]
        filtered = keyword_prefilter(entries, "deploy orders")
        assert filtered == []
