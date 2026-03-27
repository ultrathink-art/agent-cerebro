# Agent Cerebro

[![PyPI](https://img.shields.io/pypi/v/agent-cerebro)](https://pypi.org/project/agent-cerebro/)
[![Python](https://img.shields.io/pypi/pyversions/agent-cerebro)](https://pypi.org/project/agent-cerebro/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Persistent two-tier memory for AI agents. Battle-tested across 134 sessions with 10 agent roles.

**Short-term** (markdown files, always loaded) + **Long-term** (SQLite + OpenAI embeddings, searched on-demand).

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

# List categories
cerebro list coder

# Timeline — chronological view of all memories
cerebro timeline coder
cerebro timeline coder --last 7d
cerebro timeline coder --last 2w --category gotchas

# Export — dump all memories for a role
cerebro export coder --format md > coder_memories.md
cerebro export coder --format json > coder_memories.json
cerebro export coder --format json --category gotchas

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

```python
from agentrecall import MemoryStore, MemorySearch, MemoryTimeline, MemoryExport, MemoryStats, MemoryGC

# Store
store = MemoryStore()
store.store("coder", "gotchas", "kamal spawns new container", tags=["kamal", "docker"])

# Search (with optional tag filter)
search = MemorySearch()
results = search.search("coder", "gotchas", "kamal file not found")
results = search.search("coder", "gotchas", "deploy issue", tag="critical")

# Timeline
timeline = MemoryTimeline()
entries = timeline.timeline("coder", last="7d")

# Export
export = MemoryExport()
markdown = export.export("coder", fmt="md")
json_str = export.export("coder", fmt="json", category="gotchas")

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
| Max 80 lines, pruned regularly | Unlimited entries, never pruned |
| Read in full at session start | Searched on-demand per query |

### Semantic Dedup

Every `store` call embeds the text via OpenAI `text-embedding-3-small` and checks cosine similarity against all existing entries in the same role/category. Similarity > 0.92 blocks the store (raises `DuplicateError`).

Without an API key, falls back to exact text matching.

### Search

1. Embed the query
2. Compute cosine similarity against all entries with embeddings
3. Return entries above threshold (0.75), sorted by similarity
4. If no embedding matches: keyword fallback (>=50% keyword match)
5. No API key: keyword-only search
6. Optional `--tag` filter narrows results to entries with a specific tag

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

## CLI Reference

```
cerebro store <role> <category> "text" [--tags t1,t2] [--db path]
cerebro search <role> <category> "query" [--tag tagname] [--db path]
cerebro list <role> [--db path]
cerebro timeline <role> [--last 7d] [--category cat] [--limit N] [--db path]
cerebro export <role> [--format md|json] [--category cat] [--db path]
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
