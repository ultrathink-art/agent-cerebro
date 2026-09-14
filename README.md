# Agent Cerebro

[![PyPI](https://img.shields.io/pypi/v/agent-cerebro)](https://pypi.org/project/agent-cerebro/)
[![Python](https://img.shields.io/pypi/pyversions/agent-cerebro)](https://pypi.org/project/agent-cerebro/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Persistent two-tier memory for AI agents. Battle-tested across 134 sessions with 10 agent roles.

**Short-term** (markdown files, always loaded) + **Long-term** (SQLite + OpenAI embeddings, searched on-demand).

> **Cerebro Hosted (managed memory)** — same two-tier memory, but the long-term store is
> hosted and shared across machines and agents. No SQLite file to sync, no embeddings key to manage.
> [Join the waitlist →](https://ultrathink.art/cerebro/hosted?utm_source=cerebro_readme&utm_medium=oss&utm_campaign=hosted_waitlist)

## Install

```bash
pip install agent-cerebro
```

Zero required dependencies. SQLite is Python stdlib.

Optional semantic search:
```bash
pip install agent-cerebro[embeddings]
export OPENAI_API_KEY="sk-..."
```

## Quick Start

### CLI

```bash
# Initialize
cerebro init

# Store a memory (auto-dedup via cosine similarity >0.92)
cerebro store coder gotchas "kamal app exec spawns new container, use docker exec"
cerebro store social exhausted_stories "blue-green deploy order loss" --tags deploy,sqlite

# Search (semantic + keyword fallback)
cerebro search coder gotchas "kamal file not found"
cerebro search coder gotchas "deploy issue" --tag critical
cerebro search coder gotchas "deploy issue" --show-id

# Correct stale memories explicitly; history is preserved
cerebro invalidate 42 --reason "Kamal behavior changed in v2"
cerebro supersede 57 "Use docker exec for live-container queries" --reason "Old command spawned a new container"
cerebro supersede 61 "Current deployment rule" --tags deploy,current

# List categories
cerebro list coder

# Timeline — chronological view of all memories
cerebro timeline coder
cerebro timeline coder --last 7d
cerebro timeline coder --last 2w --category gotchas
cerebro timeline coder --show-id
cerebro timeline coder --include-invalidated --show-id

# Export — dump all memories for a role
cerebro export coder --format md > coder_memories.md
cerebro export coder --format json > coder_memories.json
cerebro export coder --format json --category gotchas
cerebro export coder --format json --include-invalidated > coder_audit.json

# Lossless backup — all roles, embeddings, and lifecycle history, offline
cerebro backup memory-backup.sqlite3
cerebro backup memory-backup.sqlite3 --db /path/to/memory.sqlite3
# Open the snapshot directly, including on another machine
cerebro search coder gotchas "query" --db memory-backup.sqlite3

# Stats — storage metrics and category breakdown
cerebro stats
cerebro stats coder

# Garbage collection — find and remove near-duplicates
cerebro gc coder --dry-run
cerebro gc coder --apply
cerebro gc coder --threshold 0.85 --category gotchas

# Check health
cerebro check --all
```

### Python API

For a lossless long-term database snapshot:

```python
from agentrecall import backup_database

backup_database("memory-backup.sqlite3", db_path="/path/to/memory.sqlite3")
```

`backup` captures committed data through SQLite's online backup API, including
uncheckpointed WAL writes, every role, stable IDs, embeddings, tags, and invalidated
or superseded history. It requires no API key and leaves the source schema unchanged.
The destination must be a new file in an existing directory; existing files and
symlinks are never overwritten. The snapshot is checked before publication and
created with owner-only permissions (0600 on POSIX). A missing or invalid source
fails instead of creating an empty database. CLI failures exit 2.

Use `--db memory-backup.sqlite3` to read or continue using the snapshot, or copy it
to a new memory home's `memory.sqlite3` while no processes use that destination.
Keep the original until you have verified the copy. This backs up **long-term
SQLite memory only**; copy short-term markdown files separately. Markdown/JSON
`export` remains a readable view and does not contain embeddings. The backup is
unencrypted, so protect it like the source database.

```python
from agentrecall import (
    MemoryExport,
    MemoryGC,
    MemoryLifecycle,
    MemorySearch,
    MemoryStats,
    MemoryStore,
    MemoryTimeline,
)

# Store
store = MemoryStore()
entry = store.store(
    "coder", "gotchas", "kamal spawns new container", tags=["kamal", "docker"]
)
another_entry = store.store(
    "coder", "gotchas", "use kamal app exec for live queries", tags=["kamal"]
)

# Search (with optional tag filter)
search = MemorySearch()
results = search.search("coder", "gotchas", "kamal file not found")
results = search.search("coder", "gotchas", "deploy issue", tag="critical")
# search() remains list[str]; search_records() adds stable IDs and metadata
records = search.search_records("coder", "gotchas", "deploy issue")

# Explicit lifecycle changes preserve history
lifecycle = MemoryLifecycle()
lifecycle.invalidate(entry["id"], "Kamal behavior changed in v2")
transition = lifecycle.supersede(
    another_entry["id"],
    "Use docker exec for live-container queries",
    reason="Old command spawned a new container",
)
# → {old_id, new_id, replacement}

# Timeline
timeline = MemoryTimeline()
entries = timeline.timeline("coder", last="7d")
audit_entries = timeline.timeline("coder", include_invalidated=True)

# Export
export = MemoryExport()
markdown = export.export("coder", fmt="md")
json_str = export.export("coder", fmt="json", category="gotchas")
audit_json = export.export("coder", fmt="json", include_invalidated=True)

# Stats
stats = MemoryStats()
metrics = stats.stats(role="coder")
# → {total_entries, total_with_embeddings, embedding_coverage_pct, db_size_bytes, ...}

# Garbage collection
gc = MemoryGC()
result = gc.gc("coder", dry_run=True)
# → {found: 3, removed: 0, duplicates: [...]}
result = gc.gc("coder", dry_run=False)  # actually delete
```

## How It Works

### Two-Tier Design

| Short-term (`memory/<role>.md`) | Long-term (SQLite + embeddings) |
|---|---|
| Active learnings, mistakes, feedback | Growing lists (exhausted topics, defect patterns) |
| Max 80 lines, pruned regularly | Auditable history; invalidated entries hidden by default |
| Read in full at session start | Searched on-demand per query |

### Semantic Dedup

Every `store` call embeds the text via OpenAI `text-embedding-3-small` and checks cosine similarity against active entries in the same role/category. Similarity > 0.92 blocks the store (raises `DuplicateError`); it does not silently replace either entry.

Without an API key, falls back to exact text matching.

### Memory Lifecycle

Search with `--show-id` to address a stable entry. `invalidate` soft-invalidates a
known-stale belief. `supersede` inserts a corrected entry in the same role/category
and links the invalidated original to it in one transaction. Omitting `--tags` on
`supersede` preserves the original tags; supplying it replaces them.

Normal search, timeline, export, dedup, and active counts ignore invalidated entries.
Use `timeline --include-invalidated` or `export --include-invalidated` for an audit
view with timestamps, reasons, and `superseded_by` linkage. Cerebro never interprets
a duplicate write as a truth change: two similar memories can both be valid, so
supersession is always explicit.

Opening an existing 0.4.x SQLite database automatically adds the lifecycle columns
in place. Existing rows and IDs are preserved; no manual migration command is needed.

### Search

1. Embed the query
2. Compute cosine similarity against all active entries with embeddings
3. Return entries above threshold (0.75), sorted by similarity
4. If no embedding matches: keyword fallback (>=50% keyword match)
5. No API key (or embeddings unavailable): keyword-only search
6. Optional `--tag` filter narrows results to entries with a specific tag
7. Optional `--limit N` caps output to the top-N results (keeps agent context tight)

### Garbage Collection

`cerebro gc` finds near-duplicate entries within each role/category pair:
- With embeddings: cosine similarity >= threshold (default 0.92)
- Without embeddings: exact text match (case-insensitive)
- Older entry (lower ID) is kept; newer duplicate is removed
- `--dry-run` (default) reports without deleting
- `--apply` actually removes duplicates

### Graceful Degradation

Works fully offline without an OpenAI API key:
- **Store**: exact text dedup (case-insensitive)
- **Search**: keyword matching (>=50% of query words must appear)
- **GC**: exact text match dedup only

### Network Resilience

Embedding calls are wrapped in a retry loop with exponential backoff + jitter.
Transient failures (timeouts, dropped connections, HTTP 429/5xx) are retried;
HTTP 429 honors the `Retry-After` header. After exhausting retries — or on a
non-retryable error (e.g. 401) — `store`/`search` print a warning and fall back
to keyword/exact-match instead of crashing mid-session. Auth/4xx errors are not
retried (no point burning attempts on a bad key).

Tune via `CEREBRO_EMBED_MAX_RETRIES` (default 3) and `CEREBRO_EMBED_TIMEOUT`
(seconds, default 30).

## Agent Skills

Copy `skill/agent-recall/` into your project's skills directory for use with Claude Code, Codex, Cursor, Copilot, Cline, or Goose.

```bash
cp -r skill/agent-recall/ .claude/skills/agent-recall/
```

## Configuration

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `AGENT_CEREBRO_HOME` | `~/.agent-cerebro` | Memory storage directory |
| `OPENAI_API_KEY` | (none) | OpenAI API key for embeddings |
| `UT_OPENAI_API_KEY` | (none) | Preferred over `OPENAI_API_KEY` |
| `CEREBRO_EMBED_MAX_RETRIES` | `3` | Retries on transient embedding-API failures |
| `CEREBRO_EMBED_TIMEOUT` | `30` | Per-request embedding timeout (seconds) |

## CLI Reference

```
cerebro store <role> <category> "text" [--tags t1,t2] [--db path]
cerebro search <role> <category> "query" [--tag tagname] [--limit N] [--show-id] [--db path]
cerebro invalidate <entry_id> --reason "why it is stale" [--db path]
cerebro supersede <entry_id> "replacement" [--tags t1,t2] [--reason "why"] [--db path]
cerebro list <role> [--db path]
cerebro timeline <role> [--last 7d] [--category cat] [--limit N] [--show-id] [--include-invalidated] [--db path]
cerebro export <role> [--format md|json] [--category cat] [--include-invalidated] [--db path]
cerebro backup <new-file> [--db source-path]
cerebro stats [role] [--db path]
cerebro gc <role> [--dry-run] [--apply] [--threshold 0.92] [--category cat] [--db path]
cerebro check [--fix] [--long-term] [--all] [--dir path] [--db path]
cerebro init [--dir path]
cerebro migrate [--dry-run] [--rebuild] [--dir path] [--db path]
```

`agentrecall` and `agentmemory` also work as CLI aliases.

Exit codes: `0` = success/found, `1` = not-found/validation-fail, `2` = input error.

## Migration from JSONL

If you have existing JSONL memory files:

```bash
cerebro migrate --dir /path/to/memory/
cerebro migrate --rebuild  # Re-embed entries missing embeddings
```

## Related Tools

Part of the [Ultrathink Agent Suite](https://ultrathink.art/blog/agent-toolkit-suite):

- **[Agent Architect Kit](https://github.com/ultrathink-art/agent-architect-kit)** — Multi-agent starter kit that uses Cerebro for cross-session memory
- **[Agent Orchestra](https://github.com/ultrathink-art/agent-orchestra)** — Task queue + orchestration CLI for spawning and managing agents
- **[AgentBrush](https://github.com/ultrathink-art/agentbrush)** — Image editing toolkit for AI agents

Built by an AI-run dev shop. [Read how →](https://ultrathink.art/blog/ai-agent-running-real-business)

## License

MIT
