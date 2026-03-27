"""Top-level CLI dispatcher for Agent Cerebro.

Usage:
    cerebro <command> [options]

Commands:
    store      Store an entry with semantic dedup
    search     Search entries (semantic + keyword fallback)
    list       List categories for a role
    timeline   Chronological view of memories with timestamps
    export     Export memories as markdown or JSON
    stats      Storage metrics, embedding coverage, category breakdown
    gc         Garbage collection — find/remove near-duplicate entries
    check      Validate memory files and DB health
    init       Initialize memory system for a new project
    migrate    Migrate JSONL files to SQLite
"""
from __future__ import annotations

import argparse
import os
import sys

from agentrecall import __version__


def _resolve_home() -> str:
    """Resolve memory home: AGENT_CEREBRO_HOME > AGENT_RECALL_HOME > ~/.agent-cerebro"""
    return os.environ.get(
        "AGENT_CEREBRO_HOME",
        os.environ.get("AGENT_RECALL_HOME", os.path.expanduser("~/.agent-cerebro"))
    )


def _add_store_parser(subparsers):
    p = subparsers.add_parser("store", help="Store an entry with semantic dedup")
    p.add_argument("role", help="Agent role (e.g., coder, social)")
    p.add_argument("category", help="Category (e.g., exhausted_stories, gotchas)")
    p.add_argument("text", help="Entry text to store")
    p.add_argument("--tags", help="Comma-separated tags", default="")
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_store)


def _add_search_parser(subparsers):
    p = subparsers.add_parser("search", help="Search entries (semantic + keyword)")
    p.add_argument("role", help="Agent role")
    p.add_argument("category", help="Category to search")
    p.add_argument("query", help="Search query")
    p.add_argument("--tag", help="Filter results to entries with this tag", default=None)
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_search)


def _add_list_parser(subparsers):
    p = subparsers.add_parser("list", help="List categories for a role")
    p.add_argument("role", help="Agent role")
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_list)


def _add_timeline_parser(subparsers):
    p = subparsers.add_parser("timeline", help="Chronological view of memories")
    p.add_argument("role", help="Agent role")
    p.add_argument("--last", help="Duration filter (e.g., 7d, 2w, 3m)", default=None)
    p.add_argument("--category", help="Filter to specific category", default=None)
    p.add_argument("--limit", type=int, help="Max entries (default: 100)", default=100)
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_timeline)


def _add_export_parser(subparsers):
    p = subparsers.add_parser("export", help="Export memories as markdown or JSON")
    p.add_argument("role", help="Agent role to export")
    p.add_argument("--format", dest="fmt", choices=["md", "json"], default="md",
                   help="Output format (default: md)")
    p.add_argument("--category", help="Filter to specific category", default=None)
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_export)


def _add_stats_parser(subparsers):
    p = subparsers.add_parser("stats", help="Storage metrics and statistics")
    p.add_argument("role", nargs="?", default=None, help="Agent role (omit for all)")
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_stats)


def _add_gc_parser(subparsers):
    p = subparsers.add_parser("gc", help="Garbage collect near-duplicate entries")
    p.add_argument("role", help="Agent role")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="Report duplicates without removing (default)")
    p.add_argument("--apply", action="store_true",
                   help="Actually delete duplicate entries")
    p.add_argument("--threshold", type=float, default=None,
                   help=f"Similarity threshold (default: dedup threshold)")
    p.add_argument("--category", help="Filter to specific category", default=None)
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_gc)


def _add_check_parser(subparsers):
    p = subparsers.add_parser("check", help="Validate memory files and DB health")
    p.add_argument("--fix", action="store_true", help="Auto-prune session logs")
    p.add_argument(
        "--long-term", action="store_true", dest="long_term",
        help="Check long-term memory DB health",
    )
    p.add_argument("--all", action="store_true", help="Check both short-term and long-term")
    p.add_argument("--dir", help="Memory directory path", default=None)
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_check)


def _add_init_parser(subparsers):
    p = subparsers.add_parser("init", help="Initialize memory system")
    p.add_argument("--dir", help="Directory to initialize", default=None)
    p.set_defaults(func=_cmd_init)


def _add_migrate_parser(subparsers):
    p = subparsers.add_parser("migrate", help="Migrate JSONL files to SQLite")
    p.add_argument("--dry-run", action="store_true", dest="dry_run", help="Show what would be migrated")
    p.add_argument("--rebuild", action="store_true", help="Re-embed entries missing embeddings")
    p.add_argument("--dir", help="Memory directory with JSONL files", default=None)
    p.add_argument("--db", help="Custom database path", default=None)
    p.set_defaults(func=_cmd_migrate)


def _cmd_store(args):
    from agentrecall.longterm.store import run_store

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    return run_store(args.role, args.category, args.text, tags=tags, db_path=args.db)


def _cmd_search(args):
    from agentrecall.longterm.search import run_search

    return run_search(args.role, args.category, args.query, tag=args.tag, db_path=args.db)


def _cmd_list(args):
    from agentrecall.longterm.search import run_list

    return run_list(args.role, db_path=args.db)


def _cmd_timeline(args):
    from agentrecall.core.timeline import MemoryTimeline

    tl = MemoryTimeline(db_path=args.db)
    try:
        entries = tl.timeline(
            args.role,
            last=args.last,
            category=args.category,
            limit=args.limit,
        )

        if not entries:
            print(f"No entries found for {args.role}", file=sys.stderr)
            return 1

        for entry in entries:
            tags_str = ""
            if entry["tags"]:
                tags_str = f"  [{', '.join(entry['tags'])}]"
            print(f"[{entry['created_at']}] {entry['category']}: {entry['text']}{tags_str}")

        return 0
    finally:
        tl.close()


def _cmd_export(args):
    from agentrecall.core.export import MemoryExport

    exp = MemoryExport(db_path=args.db)
    try:
        output = exp.export(args.role, fmt=args.fmt, category=args.category)
        print(output, end="")
        return 0
    finally:
        exp.close()


def _cmd_stats(args):
    from agentrecall.core.stats import MemoryStats

    ms = MemoryStats(db_path=args.db)
    try:
        s = ms.stats(role=args.role)

        role_label = args.role or "all roles"
        print(f"Memory Stats ({role_label})")
        print("=" * 50)
        print(f"  Total entries:      {s['total_entries']}")
        print(f"  With embeddings:    {s['total_with_embeddings']}")
        print(f"  Embedding coverage: {s['embedding_coverage_pct']}%")
        print(f"  Database size:      {_human_size(s['db_size_bytes'])}")

        if s["oldest_entry"]:
            print(f"  Date range:         {s['oldest_entry']} — {s['newest_entry']}")

        if not args.role and s["roles"]:
            print(f"  Roles:              {', '.join(s['roles'])}")

        if s["categories"]:
            print()
            print("Categories:")
            for cat in s["categories"]:
                emb_pct = round(100 * cat["with_embeddings"] / cat["count"], 1) if cat["count"] > 0 else 0
                print(f"  {cat['role']}/{cat['category']:<25} {cat['count']:>5} entries  ({emb_pct}% embedded)")

        return 0
    finally:
        ms.close()


def _cmd_gc(args):
    from agentrecall.core.gc import MemoryGC

    dry_run = not args.apply
    gc = MemoryGC(db_path=args.db)
    try:
        result = gc.gc(
            args.role,
            dry_run=dry_run,
            threshold=args.threshold,
            category=args.category,
        )

        if result["found"] == 0:
            print(f"No duplicates found for {args.role}")
            return 0

        mode = "DRY RUN" if dry_run else "APPLIED"
        print(f"GC [{mode}] — {result['found']} duplicate(s) found")
        print()

        for d in result["duplicates"]:
            print(f"  [{d['category']}] similarity={d['similarity']}")
            print(f"    KEEP   (#{d['keep_id']}): {d['keep_text'][:80]}")
            print(f"    REMOVE (#{d['remove_id']}): {d['remove_text'][:80]}")
            print()

        if dry_run:
            print(f"Run with --apply to remove {result['found']} duplicate(s)")
        else:
            print(f"Removed {result['removed']} duplicate(s)")

        return 0
    finally:
        gc.close()


def _cmd_check(args):
    from agentrecall.shortterm.check import check_directory, MAX_LINES, MAX_SESSION_LOG_ENTRIES
    from agentrecall.core.schema import get_db_path

    memory_dir = args.dir or _resolve_home()
    db_path = args.db or get_db_path(memory_dir)

    if args.long_term and not args.all:
        return _check_long_term(db_path)

    results = check_directory(memory_dir, fix=args.fix)

    if not results:
        print(f"No memory files found in {memory_dir}")
        if args.all:
            return _check_long_term(db_path)
        return 0

    print("Memory File Check")
    print("=" * 50)

    any_fail = False
    any_warn = False

    for r in results:
        indicator = "\u2717" if r.over_limit else "\u2713"
        status = r.status
        session_status = f"WARN (>{MAX_SESSION_LOG_ENTRIES})" if r.session_warn else "ok"
        print(
            f"{indicator} {r.name:<25} {r.line_count:>3} lines [{status}]  "
            f"sessions: {r.session_entries} [{session_status}]"
        )

        if r.fixed:
            print(f"  \u2192 Fixed ({r.line_count} \u2192 {r.new_line_count} lines)")

        if r.over_limit:
            any_fail = True
        if r.session_warn:
            any_warn = True

    print("=" * 50)

    if any_fail:
        print(f"FAILED: files exceed {MAX_LINES}-line limit")
        if not args.fix:
            print("Run `cerebro check --fix` to auto-prune session logs")
    elif any_warn:
        print(f"WARN: Some files have >{MAX_SESSION_LOG_ENTRIES} session log entries")
        if not args.fix:
            print("Run `cerebro check --fix` to auto-prune")
    else:
        print("All files within limits")

    lt_ok = True
    if args.all:
        lt_ok = _check_long_term(db_path) == 0

    if any_fail or not lt_ok:
        return 1
    return 0


def _check_long_term(db_path: str) -> int:
    """Check long-term memory DB health. Returns exit code."""
    import sqlite3

    print()
    print("Long-Term Memory DB Health")
    print("=" * 50)

    if not os.path.exists(db_path):
        print(f"\u2717 DB not found: {db_path}")
        print("  Long-term memory not initialized. Run `cerebro init` to create.")
        return 1

    db_size = os.path.getsize(db_path)
    print(f"\u2713 DB exists ({db_size / 1024:.1f} KB)")

    try:
        conn = sqlite3.connect(db_path)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity == "ok":
            print("\u2713 Integrity: ok")
        else:
            print(f"\u2717 Integrity: {integrity}")
            conn.close()
            return 1

        rows = conn.execute(
            "SELECT role, category, COUNT(*) as cnt, "
            "SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_emb "
            "FROM entries GROUP BY role, category ORDER BY role, category"
        ).fetchall()

        if not rows:
            print("  No entries yet (DB is empty)")
            conn.close()
            return 0

        total_entries = 0
        total_with_emb = 0
        lt_fail = False

        for role, category, cnt, with_emb in rows:
            total_entries += cnt
            total_with_emb += with_emb
            pct = int(100 * with_emb / cnt) if cnt > 0 else 0
            if pct == 100:
                indicator = "\u2713"
            elif pct >= 50:
                indicator = "\u26A0"
            else:
                indicator = "\u2717"
                lt_fail = True
            print(
                f"{indicator} {role}/{category:<25} {cnt:>5} entries  "
                f"embeddings: {with_emb}/{cnt} ({pct}%)"
            )

        total_pct = int(100 * total_with_emb / total_entries) if total_entries > 0 else 0
        print("-" * 50)
        print(f"  Total: {total_entries} entries, {total_with_emb} with embeddings ({total_pct}%)")

        if total_pct < 100:
            print("  \u26A0 Some entries lack embeddings. Set OPENAI_API_KEY to enable.")

        conn.close()
        return 1 if lt_fail else 0

    except sqlite3.Error as e:
        print(f"\u2717 DB error: {e}")
        return 1


def _cmd_init(args):
    from agentrecall.core.schema import get_connection, get_db_path
    from agentrecall.shortterm.template import generate_template

    memory_home = args.dir or _resolve_home()
    os.makedirs(memory_home, exist_ok=True)

    db_path = get_db_path(memory_home)
    get_connection(db_path)

    print(f"Initialized Agent Cerebro at {memory_home}")
    print(f"  Database: {db_path}")
    print()
    print("Create a memory file for an agent role:")
    print(f"  echo '{generate_template('coder').splitlines()[0]}' > {memory_home}/coder.md")
    return 0


def _cmd_migrate(args):
    from agentrecall.longterm.migrate import run_migrate, run_rebuild
    from agentrecall.core.schema import get_db_path

    memory_dir = args.dir or _resolve_home()
    db_path = args.db or get_db_path(memory_dir)

    if args.rebuild:
        return run_rebuild(dry_run=args.dry_run, db_path=db_path)
    return run_migrate(memory_dir, dry_run=args.dry_run, db_path=db_path)


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="cerebro",
        description="Agent Cerebro — persistent two-tier memory for AI agents",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"agent-cerebro {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _add_store_parser(subparsers)
    _add_search_parser(subparsers)
    _add_list_parser(subparsers)
    _add_timeline_parser(subparsers)
    _add_export_parser(subparsers)
    _add_stats_parser(subparsers)
    _add_gc_parser(subparsers)
    _add_check_parser(subparsers)
    _add_init_parser(subparsers)
    _add_migrate_parser(subparsers)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    exit_code = args.func(args)
    sys.exit(exit_code or 0)
