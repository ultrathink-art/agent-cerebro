"""Tests for MemorySearch and keyword fallback."""
import math

import pytest

from agentrecall.core.search import MemorySearch, keyword_fallback, keyword_prefilter
from agentrecall.core.store import MemoryStore
from conftest import fake_embedding, make_embed_fn, null_embed_fn


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


class TestMixedCoverage:
    def _seed(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        # Outage-saved entries precede semantic entries in insertion order.
        store.store("r", "c", "deploy offline lesson", tags=["ops"], embed_fn=null_embed_fn)
        store.store("r", "c", "deploy unrelated tag", tags=["other"], embed_fn=null_embed_fn)
        store.store("r", "c", "irrelevant offline lesson", tags=["ops"], embed_fn=null_embed_fn)
        store.store("r", "c", "deploy obsolete lesson", tags=["ops"], embed_fn=null_embed_fn)
        store.conn.execute("UPDATE entries SET invalidated_at = '2026-10-19' WHERE text = 'deploy obsolete lesson'")
        store.conn.commit()
        store.store("r", "c", "semantic operational lesson", tags=["ops"], embed_fn=make_embed_fn(0.1))
        store.close()

    def test_outage_memories_survive_provider_recovery(self, tmp_db):
        self._seed(tmp_db)
        search = MemorySearch(db_path=tmp_db)
        records = search.search_records("r", "c", "deploy", tag="ops", embed_fn=make_embed_fn(0.1))
        assert [r["text"] for r in records] == ["semantic operational lesson", "deploy offline lesson"]
        assert all(r["id"] > 0 and r["tags"] == ["ops"] and "embedding" not in r for r in records)
        assert len({r["id"] for r in records}) == 2
        search.close()

    @pytest.mark.parametrize("limit,expected", [(1, 1), (2, 2), (0, 2), (None, 2)])
    def test_limit_applies_after_combining_results(self, tmp_db, limit, expected):
        self._seed(tmp_db)
        search = MemorySearch(db_path=tmp_db)
        results = search.search("r", "c", "deploy", tag="ops", embed_fn=make_embed_fn(0.1), limit=limit)
        assert len(results) == expected
        assert results[0] == "semantic operational lesson"
        search.close()

    def test_unembedded_filtered_category_never_calls_provider(self, tmp_db):
        self._seed(tmp_db)
        def unexpected_call(text):
            pytest.fail("unembedded-only candidates must not call the embedding provider")
        search = MemorySearch(db_path=tmp_db)
        assert search.search("r", "c", "deploy", tag="other", embed_fn=unexpected_call) == ["deploy unrelated tag"]
        assert search.search("r", "c", "missing", tag="other", embed_fn=unexpected_call) == []
        search.close()

    def test_outage_fallback_does_not_duplicate_unembedded_results(self, tmp_db):
        self._seed(tmp_db)
        search = MemorySearch(db_path=tmp_db)
        assert search.search("r", "c", "deploy", tag="ops", embed_fn=null_embed_fn) == ["deploy offline lesson"]
        search.close()


class TestSearchLimit:
    def _seed(self, tmp_db):
        """Insert 3 entries sharing one embedding (all match the query)."""
        import sqlite3

        from agentrecall.core.embeddings import pack_embedding
        from conftest import fake_embedding

        blob = pack_embedding(fake_embedding(0.1))
        conn = sqlite3.connect(tmp_db)
        for txt in ("deploy order one", "deploy order two", "deploy order three"):
            conn.execute(
                "INSERT INTO entries (role, category, text, embedding, tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("r", "c", txt, blob, "[]", "2026-01-01"),
            )
        conn.commit()
        conn.close()

    def test_limit_caps_results(self, tmp_db):
        self._seed(tmp_db)
        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy", embed_fn=make_embed_fn(0.1), limit=2)
        assert len(result) == 2
        search.close()

    def test_no_limit_returns_all(self, tmp_db):
        self._seed(tmp_db)
        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy", embed_fn=make_embed_fn(0.1))
        assert len(result) == 3
        search.close()

    def test_limit_caps_keyword_fallback(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order one", embed_fn=null_embed_fn)
        store.store("r", "c", "deploy order two", embed_fn=null_embed_fn)
        store.close()
        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy order", embed_fn=null_embed_fn, limit=1)
        assert len(result) == 1
        search.close()

    def test_zero_limit_is_no_cap(self, tmp_db):
        self._seed(tmp_db)
        search = MemorySearch(db_path=tmp_db)
        result = search.search("r", "c", "deploy", embed_fn=make_embed_fn(0.1), limit=0)
        assert len(result) == 3
        search.close()

    def test_cli_search_accepts_limit_flag(self, tmp_db):
        self._seed(tmp_db)
        from agentrecall.longterm.search import run_search

        # Embeddings unavailable in this path → keyword fallback, still limited.
        rc = run_search("r", "c", "deploy", limit=1, db_path=tmp_db)
        assert rc == 0


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
