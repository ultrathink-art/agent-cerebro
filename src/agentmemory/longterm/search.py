"""Long-term search CLI handler."""
from __future__ import annotations

import sys
from typing import Optional

from agentmemory.core.search import MemorySearch
from agentmemory.core.store import MemoryStore


def run_search(
    role: str,
    category: str,
    query: str,
    db_path: Optional[str] = None,
) -> int:
    """Search entries. Returns exit code (0=found, 1=not found)."""
    search = MemorySearch(db_path=db_path)
    try:
        count = search.count(role, category)
        if count == 0:
            print(f"No entries found for {role}/{category}", file=sys.stderr)
            return 1

        matches = search.search(role, category, query)
        if not matches:
            print(f"No matches for: {query}", file=sys.stderr)
            print(f"  (searched {count} entries in {role}/{category})", file=sys.stderr)
            return 1

        for m in matches:
            print(m)
        return 0
    finally:
        search.close()


def run_list(role: str, db_path: Optional[str] = None) -> int:
    """List categories for a role. Returns exit code."""
    store = MemoryStore(db_path=db_path)
    try:
        categories = store.list_categories(role)
        if not categories:
            print(f"No categories found for role: {role}")
            return 0
        print(f"Categories for {role}:")
        for c in categories:
            print(f"  {c}")
        return 0
    finally:
        store.close()
