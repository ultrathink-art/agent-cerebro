"""Tests for tag filtering in search."""
import pytest

from agentrecall.core.search import MemorySearch
from agentrecall.core.store import MemoryStore
from conftest import make_embed_fn, null_embed_fn


class TestSearchTagFilter:
    def test_tag_filter_narrows_results(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", tags=["deploy", "critical"],
                    embed_fn=null_embed_fn)
        store.store("r", "c", "sticker deploy issue", tags=["design"],
                    embed_fn=null_embed_fn)
        store.close()

        search = MemorySearch(db_path=tmp_db)
        all_results = search.search("r", "c", "deploy", embed_fn=null_embed_fn)
        tagged_results = search.search("r", "c", "deploy", embed_fn=null_embed_fn, tag="critical")

        assert len(all_results) == 2
        assert len(tagged_results) == 1
        assert "deploy order loss" in tagged_results
        search.close()

    def test_tag_filter_no_match(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "deploy order loss", tags=["deploy"],
                    embed_fn=null_embed_fn)
        store.close()

        search = MemorySearch(db_path=tmp_db)
        results = search.search("r", "c", "deploy", embed_fn=null_embed_fn, tag="nonexistent")
        assert results == []
        search.close()

    def test_tag_filter_with_embeddings(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "entry A", tags=["important"],
                    embed_fn=make_embed_fn(0.1))
        store.store("r", "c", "entry B", tags=["minor"],
                    embed_fn=make_embed_fn(0.1008))
        store.close()

        search = MemorySearch(db_path=tmp_db)
        results = search.search("r", "c", "entry", embed_fn=make_embed_fn(0.1), tag="important")
        assert len(results) == 1
        assert "entry A" in results
        search.close()

    def test_no_tag_returns_all(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "entry A", tags=["tag1"], embed_fn=null_embed_fn)
        store.store("r", "c", "entry B", tags=["tag2"], embed_fn=null_embed_fn)
        store.close()

        search = MemorySearch(db_path=tmp_db)
        results = search.search("r", "c", "entry", embed_fn=null_embed_fn)
        assert len(results) == 2
        search.close()

    def test_tag_filter_empty_tags(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "entry with no tags", embed_fn=null_embed_fn)
        store.store("r", "c", "entry with tag", tags=["important"],
                    embed_fn=null_embed_fn)
        store.close()

        search = MemorySearch(db_path=tmp_db)
        results = search.search("r", "c", "entry", embed_fn=null_embed_fn, tag="important")
        assert len(results) == 1
        assert "entry with tag" in results
        search.close()
