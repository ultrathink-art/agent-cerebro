#!/usr/bin/env python3
"""Search long-term agent memory.

Usage:
    python search.py <role> <category> "query"
    python search.py <role> --list
"""
import sys

from agentmemory.longterm.search import run_search, run_list


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: python search.py <role> <category> \"query\"", file=sys.stderr)
        print("       python search.py <role> --list", file=sys.stderr)
        sys.exit(2)

    role = args[0]

    if args[1] == "--list":
        sys.exit(run_list(role))

    if len(args) < 3:
        print("ERROR: query is required", file=sys.stderr)
        sys.exit(2)

    category = args[1]
    query = " ".join(args[2:])

    sys.exit(run_search(role, category, query))


if __name__ == "__main__":
    main()
