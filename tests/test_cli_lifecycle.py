"""CLI coverage for addressable and auditable memory lifecycle commands."""
import json

import pytest

from agentrecall.cli import main
from agentrecall.core.store import MemoryStore
from conftest import null_embed_fn


def _run(argv, expected_code=0):
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == expected_code


class TestAddressableOutput:
    def test_search_show_id_is_opt_in(self, tmp_db, monkeypatch, capsys):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        store = MemoryStore(db_path=tmp_db)
        entry = store.store(
            "coder", "gotchas", "addressable memory", embed_fn=null_embed_fn
        )
        store.close()

        _run(["search", "coder", "gotchas", "addressable", "--db", tmp_db])
        captured = capsys.readouterr()
        assert captured.out == "addressable memory\n"

        _run([
            "search", "coder", "gotchas", "addressable",
            "--show-id", "--db", tmp_db,
        ])
        captured = capsys.readouterr()
        assert captured.out == f"#{entry['id']}: addressable memory\n"

    def test_timeline_show_id_is_opt_in(self, tmp_db, capsys):
        store = MemoryStore(db_path=tmp_db)
        entry = store.store("coder", "gotchas", "timeline memory", embed_fn=null_embed_fn)
        store.close()

        _run(["timeline", "coder", "--db", tmp_db])
        captured = capsys.readouterr()
        assert captured.out.startswith(f"[{entry['created_at']}] gotchas:")
        assert f"#{entry['id']}" not in captured.out

        _run(["timeline", "coder", "--show-id", "--db", tmp_db])
        captured = capsys.readouterr()
        assert captured.out.startswith(
            f"#{entry['id']} [{entry['created_at']}] gotchas:"
        )


class TestLifecycleCLI:
    def test_supersede_then_invalidate_with_audit_history(
        self, tmp_db, monkeypatch, capsys
    ):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        store = MemoryStore(db_path=tmp_db)
        old = store.store(
            "social", "guidelines", "old belief", tags=["policy"],
            embed_fn=null_embed_fn,
        )
        store.close()

        _run([
            "supersede", str(old["id"]), "corrected belief",
            "--reason", "Rule changed", "--db", tmp_db,
        ])
        captured = capsys.readouterr()
        assert captured.out == f"#{old['id']} -> #{old['id'] + 1}\n"
        new_id = old["id"] + 1

        _run([
            "search", "social", "guidelines", "belief",
            "--show-id", "--db", tmp_db,
        ])
        captured = capsys.readouterr()
        assert f"#{new_id}: corrected belief" in captured.out
        assert "old belief" not in captured.out

        _run([
            "invalidate", str(new_id), "--reason", "No longer current",
            "--db", tmp_db,
        ])
        captured = capsys.readouterr()
        assert captured.out == f"Invalidated entry #{new_id}\n"

        _run([
            "search", "social", "guidelines", "belief", "--db", tmp_db,
        ], expected_code=1)
        captured = capsys.readouterr()
        assert "old belief" not in captured.out
        assert "corrected belief" not in captured.out

        _run([
            "timeline", "social", "--include-invalidated", "--show-id",
            "--db", tmp_db,
        ])
        captured = capsys.readouterr()
        assert f"#{old['id']} " in captured.out
        assert f"superseded by #{new_id}" in captured.out
        assert "reason: Rule changed" in captured.out
        assert f"#{new_id} " in captured.out
        assert "reason: No longer current" in captured.out

        _run([
            "export", "social", "--format", "json", "--db", tmp_db,
        ])
        normal = json.loads(capsys.readouterr().out)
        assert normal == []

        _run([
            "export", "social", "--format", "json",
            "--include-invalidated", "--db", tmp_db,
        ])
        audit = json.loads(capsys.readouterr().out)
        assert [entry["id"] for entry in audit] == [old["id"], new_id]
        assert audit[0]["status"] == "invalidated"
        assert audit[0]["superseded_by"] == new_id
        assert audit[1]["status"] == "invalidated"

    def test_invalidate_errors_are_nonzero_and_precise(self, tmp_db, capsys):
        _run([
            "invalidate", "999", "--reason", "Missing", "--db", tmp_db,
        ], expected_code=1)
        assert "Error: Entry #999 not found" in capsys.readouterr().err

        store = MemoryStore(db_path=tmp_db)
        entry = store.store("coder", "gotchas", "old", embed_fn=null_embed_fn)
        store.close()
        _run([
            "invalidate", str(entry["id"]), "--reason", "Old", "--db", tmp_db,
        ])
        capsys.readouterr()
        _run([
            "invalidate", str(entry["id"]), "--reason", "Old again",
            "--db", tmp_db,
        ], expected_code=1)
        assert (
            f"Error: Entry #{entry['id']} is already invalidated"
            in capsys.readouterr().err
        )


class TestCLIHelpAndVersion:
    def test_help_lists_lifecycle_commands(self, capsys):
        _run(["--help"])
        output = capsys.readouterr().out
        assert "invalidate" in output
        assert "supersede" in output

        _run(["timeline", "--help"])
        assert "--include-invalidated" in capsys.readouterr().out

    def test_version_is_060(self, capsys):
        _run(["--version"])
        assert capsys.readouterr().out == "agent-cerebro 0.6.0\n"
