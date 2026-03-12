"""Migrate JSONL files to SQLite + embeddings."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Any, Optional

from agentmemory.core.embeddings import (
    get_embeddings_batch,
    pack_embedding,
)
from agentmemory.core.schema import get_connection


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load entries from a JSONL file, skipping malformed lines."""
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def run_migrate(
    memory_dir: str,
    dry_run: bool = False,
    db_path: Optional[str] = None,
) -> int:
    """Migrate all JSONL files under memory_dir to SQLite."""
    import glob

    pattern = os.path.join(memory_dir, "**", "*.jsonl")
    files = glob.glob(pattern, recursive=True)

    if not files:
        print(f"No JSONL files found in {memory_dir}")
        return 0

    conn = get_connection(db_path)
    total_entries = 0
    total_migrated = 0
    total_skipped = 0

    for path in sorted(files):
        relative = os.path.relpath(path, memory_dir)
        parts = Path(relative).parts
        if len(parts) < 2:
            continue

        role = "/".join(parts[:-1])
        category = Path(parts[-1]).stem

        entries = load_jsonl(path)
        total_entries += len(entries)
        print(f"{role}/{category}: {len(entries)} entries")

        if dry_run:
            print(f"  (dry-run -- would migrate {len(entries)} entries)")
            continue

        texts = [e["text"] for e in entries]
        embeddings = None

        try:
            embeddings = get_embeddings_batch(texts)
            if embeddings:
                print(f"  Embedded {len(texts)} entries via OpenAI")
        except Exception as e:
            print(
                f"  WARNING: Embedding failed ({e}) -- storing without embeddings",
                file=sys.stderr,
            )

        file_migrated = 0
        file_skipped = 0

        for idx, entry in enumerate(entries):
            text = entry["text"]
            tags = entry.get("tags", [])
            created = entry.get("created_at", date.today().isoformat())

            existing = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE role = ? AND category = ? AND text = ?",
                (role, category, text),
            ).fetchone()

            if existing and existing[0] > 0:
                file_skipped += 1
                total_skipped += 1
                continue

            emb = embeddings[idx] if embeddings else None
            emb_blob = pack_embedding(emb) if emb else None
            tags_json = json.dumps(tags if isinstance(tags, list) else [])

            conn.execute(
                "INSERT INTO entries (role, category, text, embedding, tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (role, category, text, emb_blob, tags_json, created),
            )
            file_migrated += 1
            total_migrated += 1

        conn.commit()
        print(f"  Migrated: {file_migrated}, Skipped: {file_skipped}")

    print()
    print("=== Migration Summary ===")
    print(f"  JSONL files: {len(files)}")
    print(f"  Total entries: {total_entries}")
    print(f"  Migrated: {total_migrated}")
    print(f"  Skipped: {total_skipped}")

    db_count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    print(f"  DB total: {db_count}")

    if not dry_run:
        print()
        print("JSONL files preserved. Remove manually after verifying:")
        for f in files:
            print(f"  rm {f}")

    return 0


def run_rebuild(
    dry_run: bool = False,
    db_path: Optional[str] = None,
) -> int:
    """Re-embed entries missing embeddings."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT id, text FROM entries WHERE embedding IS NULL"
    ).fetchall()

    if not rows:
        print("All entries have embeddings.")
        return 0

    print(f"Found {len(rows)} entries without embeddings.")

    if dry_run:
        print(f"(dry-run -- would embed {len(rows)} entries)")
        return 0

    texts = [r[1] for r in rows]
    try:
        embeddings = get_embeddings_batch(texts)
    except Exception as e:
        print(f"ERROR: Batch embed failed: {e}", file=sys.stderr)
        return 1

    if not embeddings:
        print("ERROR: No API key available for embedding", file=sys.stderr)
        return 1

    for idx, row in enumerate(rows):
        emb_blob = pack_embedding(embeddings[idx])
        conn.execute(
            "UPDATE entries SET embedding = ? WHERE id = ?",
            (emb_blob, row[0]),
        )

    conn.commit()
    print(f"Embedded {len(rows)} entries.")
    return 0
