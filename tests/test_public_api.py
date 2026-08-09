"""Tests that the public API (from agentrecall import ...) works correctly."""
import pytest

from agentrecall import DuplicateError, MemoryLifecycle, MemorySearch, MemoryStore
from agentrecall.core.store import DuplicateError as CoreDuplicateError
from conftest import null_embed_fn


class TestDuplicateErrorIdentity:
    def test_public_api_exports_same_class_as_core(self):
        assert DuplicateError is CoreDuplicateError

    def test_public_api_catches_store_duplicate(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        store.store("r", "c", "some text", embed_fn=null_embed_fn)

        with pytest.raises(DuplicateError):
            store.store("r", "c", "some text", embed_fn=null_embed_fn)
        store.close()

    def test_duplicate_error_in_all(self):
        import agentrecall
        assert "DuplicateError" in agentrecall.__all__


class TestSearchCompatibility:
    def test_search_stays_list_of_strings_and_records_add_ids(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        entry = store.store("r", "c", "addressable memory", embed_fn=null_embed_fn)
        search = MemorySearch(db_path=tmp_db)

        texts = search.search("r", "c", "addressable", embed_fn=null_embed_fn)
        records = search.search_records(
            "r", "c", "addressable", embed_fn=null_embed_fn
        )

        assert texts == ["addressable memory"]
        assert records == [{
            "id": entry["id"],
            "role": "r",
            "category": "c",
            "text": "addressable memory",
            "tags": [],
            "created_at": entry["created_at"],
        }]

        search.close()
        store.close()

    def test_lifecycle_is_exported(self):
        import agentrecall
        assert "MemoryLifecycle" in agentrecall.__all__
        assert agentrecall.MemoryLifecycle is MemoryLifecycle
