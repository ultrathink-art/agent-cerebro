"""Long-term store CLI handler."""
from __future__ import annotations

import sys
from typing import List, Optional

from agentmemory.core.store import MemoryStore, DuplicateError


def run_store(
    role: str,
    category: str,
    text: str,
    tags: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> int:
    """Store an entry. Returns exit code (0=success, 1=duplicate/error)."""
    store = MemoryStore(db_path=db_path)
    try:
        entry = store.store(role, category, text, tags=tags)
        count = store.count(role, category)
        print(f"STORED: {text}")
        print(f"  category: {role}/{category} ({count} entries)")
        if entry["tags"]:
            print(f"  tags: {', '.join(entry['tags'])}")
        return 0
    except DuplicateError as e:
        print(f"DUPLICATE: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        store.close()
