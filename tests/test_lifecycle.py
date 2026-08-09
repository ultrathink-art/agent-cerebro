"""Tests for soft invalidation and atomic supersession."""
import json
import sqlite3

import pytest

from agentrecall.core.export import MemoryExport
from agentrecall.core.lifecycle import (
    AlreadyInvalidatedError,
    EntryNotFoundError,
    MemoryLifecycle,
)
from agentrecall.core.search import MemorySearch
from agentrecall.core.store import DuplicateError, MemoryStore
from agentrecall.core.timeline import MemoryTimeline
from conftest import make_embed_fn, null_embed_fn


class TestInvalidation:
    def test_invalidated_entry_is_inactive_and_can_be_stored_again(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        old = store.store("coder", "gotchas", "stale belief", embed_fn=null_embed_fn)

        lifecycle = MemoryLifecycle(db_path=tmp_db)
        result = lifecycle.invalidate(old["id"], "The underlying rule changed")

        assert result["id"] == old["id"]
        assert result["invalidation_reason"] == "The underlying rule changed"
        assert result["invalidated_at"]

        search = MemorySearch(db_path=tmp_db)
        assert search.search(
            "coder", "gotchas", "stale belief", embed_fn=null_embed_fn
        ) == []
        assert search.count("coder", "gotchas") == 0
        replacement = store.store(
            "coder", "gotchas", "stale belief", embed_fn=null_embed_fn
        )
        assert replacement["id"] != old["id"]

        search.close()
        lifecycle.close()
        store.close()

    def test_invalidated_embedding_does_not_block_semantic_dedup(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        old = store.store(
            "coder", "gotchas", "old wording", embed_fn=make_embed_fn(0.1)
        )
        lifecycle = MemoryLifecycle(db_path=tmp_db)
        lifecycle.invalidate(old["id"], "Incorrect")

        new = store.store(
            "coder", "gotchas", "corrected wording", embed_fn=make_embed_fn(0.1)
        )
        assert new["id"] != old["id"]

        lifecycle.close()
        store.close()

    def test_missing_and_already_invalidated_are_precise_errors(self, tmp_db):
        lifecycle = MemoryLifecycle(db_path=tmp_db)
        with pytest.raises(EntryNotFoundError, match=r"Entry #999 not found"):
            lifecycle.invalidate(999, "Missing")

        store = MemoryStore(db_path=tmp_db)
        entry = store.store("coder", "gotchas", "old", embed_fn=null_embed_fn)
        lifecycle.invalidate(entry["id"], "Outdated")
        with pytest.raises(
            AlreadyInvalidatedError,
            match=rf"Entry #{entry['id']} is already invalidated",
        ):
            lifecycle.invalidate(entry["id"], "Still outdated")

        store.close()
        lifecycle.close()

    def test_audit_timeline_and_export_preserve_metadata(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        old = store.store(
            "coder", "gotchas", "old belief", tags=["old"], embed_fn=null_embed_fn
        )
        active = store.store(
            "coder", "gotchas", "active belief", tags=["current"],
            embed_fn=null_embed_fn,
        )
        lifecycle = MemoryLifecycle(db_path=tmp_db)
        lifecycle.invalidate(old["id"], "Source changed")

        timeline = MemoryTimeline(db_path=tmp_db)
        assert [entry["id"] for entry in timeline.timeline("coder")] == [active["id"]]
        audit_entries = timeline.timeline("coder", include_invalidated=True)
        invalidated = next(entry for entry in audit_entries if entry["id"] == old["id"])
        assert invalidated["status"] == "invalidated"
        assert invalidated["invalidation_reason"] == "Source changed"
        assert invalidated["superseded_by"] is None

        exporter = MemoryExport(db_path=tmp_db)
        normal = json.loads(exporter.export("coder", fmt="json"))
        assert [entry["id"] for entry in normal] == [active["id"]]
        assert "status" not in normal[0]

        audit = json.loads(
            exporter.export("coder", fmt="json", include_invalidated=True)
        )
        audit_old = next(entry for entry in audit if entry["id"] == old["id"])
        assert audit_old["status"] == "invalidated"
        assert audit_old["invalidated_at"]
        assert audit_old["invalidation_reason"] == "Source changed"

        markdown = exporter.export(
            "coder", fmt="md", include_invalidated=True
        )
        assert f"#{old['id']}" in markdown
        assert "INVALIDATED" in markdown
        assert "reason: Source changed" in markdown

        exporter.close()
        timeline.close()
        lifecycle.close()
        store.close()


class TestSupersession:
    def test_similar_replacement_bypasses_target_and_inherits_context(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        old = store.store(
            "social",
            "guidelines",
            "old belief",
            tags=["policy", "social"],
            embed_fn=make_embed_fn(0.1),
        )
        lifecycle = MemoryLifecycle(db_path=tmp_db)

        result = lifecycle.supersede(
            old["id"],
            "corrected belief",
            reason="Policy changed",
            embed_fn=make_embed_fn(0.1),
        )

        assert result["old_id"] == old["id"]
        assert result["new_id"] != old["id"]
        assert result["replacement"]["role"] == "social"
        assert result["replacement"]["category"] == "guidelines"
        assert result["replacement"]["tags"] == ["policy", "social"]

        rows = lifecycle.conn.execute(
            "SELECT id, invalidated_at, invalidation_reason, superseded_by "
            "FROM entries ORDER BY id"
        ).fetchall()
        assert rows[0][1]
        assert rows[0][2] == "Policy changed"
        assert rows[0][3] == result["new_id"]
        assert rows[1][1] is None

        search = MemorySearch(db_path=tmp_db)
        matches = search.search_records(
            "social", "guidelines", "belief", embed_fn=make_embed_fn(0.1)
        )
        assert [entry["id"] for entry in matches] == [result["new_id"]]

        search.close()
        lifecycle.close()
        store.close()

    def test_supersede_can_override_tags(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        old = store.store(
            "coder", "gotchas", "old", tags=["old"], embed_fn=null_embed_fn
        )
        lifecycle = MemoryLifecycle(db_path=tmp_db)
        result = lifecycle.supersede(
            old["id"], "new", tags=["new", "verified"], embed_fn=null_embed_fn
        )
        assert result["replacement"]["tags"] == ["new", "verified"]

        lifecycle.close()
        store.close()

    def test_other_active_duplicate_blocks_entire_transition(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        old = store.store(
            "coder", "gotchas", "target", embed_fn=make_embed_fn(0.1)
        )
        other = store.store(
            "coder", "gotchas", "other active", embed_fn=make_embed_fn(5.0)
        )
        lifecycle = MemoryLifecycle(db_path=tmp_db)

        with pytest.raises(DuplicateError, match="other active"):
            lifecycle.supersede(
                old["id"], "replacement", embed_fn=make_embed_fn(5.0)
            )

        rows = lifecycle.conn.execute(
            "SELECT id, invalidated_at FROM entries ORDER BY id"
        ).fetchall()
        assert rows == [(old["id"], None), (other["id"], None)]

        lifecycle.close()
        store.close()

    def test_update_failure_rolls_back_insert(self, tmp_db):
        store = MemoryStore(db_path=tmp_db)
        old = store.store("coder", "gotchas", "old", embed_fn=null_embed_fn)
        store.conn.execute(
            "CREATE TRIGGER reject_lifecycle_update "
            "BEFORE UPDATE ON entries "
            f"WHEN OLD.id = {old['id']} "
            "BEGIN SELECT RAISE(ABORT, 'blocked update'); END"
        )
        store.conn.commit()
        lifecycle = MemoryLifecycle(db_path=tmp_db)

        with pytest.raises(sqlite3.IntegrityError, match="blocked update"):
            lifecycle.supersede(
                old["id"], "new", embed_fn=null_embed_fn
            )

        rows = lifecycle.conn.execute(
            "SELECT id, text, invalidated_at FROM entries"
        ).fetchall()
        assert rows == [(old["id"], "old", None)]

        lifecycle.close()
        store.close()
