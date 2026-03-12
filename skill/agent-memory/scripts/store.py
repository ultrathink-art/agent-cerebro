#!/usr/bin/env python3
"""Store an entry in long-term agent memory.

Usage:
    python store.py <role> <category> "text" [--tags tag1,tag2]
"""
import sys

from agentmemory.longterm.store import run_store


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        print("Usage: python store.py <role> <category> \"text\" [--tags tag1,tag2]", file=sys.stderr)
        sys.exit(2)

    role = args[0]
    category = args[1]

    tags = []
    remaining = args[2:]
    if "--tags" in remaining:
        idx = remaining.index("--tags")
        if idx + 1 < len(remaining):
            tags = [t.strip() for t in remaining[idx + 1].split(",") if t.strip()]
            remaining = remaining[:idx] + remaining[idx + 2:]

    text = " ".join(remaining)
    if not text.strip():
        print("ERROR: text is required", file=sys.stderr)
        sys.exit(2)

    sys.exit(run_store(role, category, text, tags=tags))


if __name__ == "__main__":
    main()
