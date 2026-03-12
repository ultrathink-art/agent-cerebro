#!/usr/bin/env python3
"""Initialize agentmemory for a new project.

Usage:
    python setup.py [--dir PATH]
"""
import sys

from agentmemory.cli import main as cli_main


def main():
    args = ["init"] + sys.argv[1:]
    try:
        cli_main(args)
    except SystemExit as e:
        sys.exit(e.code)


if __name__ == "__main__":
    main()
