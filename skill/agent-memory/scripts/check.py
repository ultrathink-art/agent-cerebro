#!/usr/bin/env python3
"""Check memory health (short-term file limits + DB integrity).

Usage:
    python check.py [--fix] [--long-term] [--all] [--dir PATH]
"""
import sys

from agentmemory.cli import main as cli_main


def main():
    args = ["check"] + sys.argv[1:]
    try:
        cli_main(args)
    except SystemExit as e:
        sys.exit(e.code)


if __name__ == "__main__":
    main()
