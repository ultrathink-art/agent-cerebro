# AgentMemory

[![PyPI](https://img.shields.io/pypi/v/agentmemory)](https://pypi.org/project/agentmemory/)
[![Python](https://img.shields.io/pypi/pyversions/agentmemory)](https://pypi.org/project/agentmemory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Persistent two-tier memory for AI agents. Battle-tested across 134 sessions with 10 agent roles.

**Short-term** (markdown files, always loaded) + **Long-term** (SQLite + OpenAI embeddings, searched on-demand).

## Install

```bash
pip install agentmemory
```

Zero required dependencies. SQLite is Python stdlib.

Optional semantic search:
```bash
pip install agentmemory[embeddings]
export OPENAI_API_KEY="sk-..."
```

## Quick Start

### CLI

```bash
# Initialize
agentmemory init

# Store a memory (auto-dedup via cosine similarity >0.92)
agentmemory store coder gotchas "kamal app exec spawns new container, use docker exec"
agentmemory store social exhausted_stories "blue-green deploy order loss" --tags deploy,sqlite

# Search (semantic + keyword fallback)
agentmemory search coder gotchas "kamal file not found"

# List categories
agentmemory list coder

# Check health
agentmemory check --all
```

### Python API

```python
from agentmemory import MemoryStore, MemorySearch

# Store
store = MemoryStore()
store.store("coder", "gotchas", "kamal spawns new container", tags=["kamal", "docker"])

# Search
search = MemorySearch()
results = search.search("coder", "gotchas", "kamal file not found")
for text in results:
    print(text)

# List categories
categories = store.list_categories("coder")
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

### Graceful Degradation

Works fully offline without an OpenAI API key:
- **Store**: exact text dedup (case-insensitive)
- **Search**: keyword matching (>=50% of query words must appear)

## Agent Skills

Copy `skill/agent-memory/` into your project's skills directory for use with Claude Code, Codex, Cursor, Copilot, Cline, or Goose.

```bash
cp -r skill/agent-memory/ .claude/skills/agent-memory/
```

## Configuration

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `AGENT_MEMORY_HOME` | `~/.agentmemory` | Memory storage directory |
| `OPENAI_API_KEY` | (none) | OpenAI API key for embeddings |
| `UT_OPENAI_API_KEY` | (none) | Preferred over `OPENAI_API_KEY` |

## CLI Reference

```
agentmemory store <role> <category> "text" [--tags t1,t2] [--db path]
agentmemory search <role> <category> "query" [--db path]
agentmemory list <role> [--db path]
agentmemory check [--fix] [--long-term] [--all] [--dir path] [--db path]
agentmemory init [--dir path]
agentmemory migrate [--dry-run] [--rebuild] [--dir path] [--db path]
```

Exit codes: `0` = success/found, `1` = not-found/validation-fail, `2` = input error.

## Migration from JSONL

If you have existing JSONL memory files:

```bash
agentmemory migrate --dir /path/to/memory/
agentmemory migrate --rebuild  # Re-embed entries missing embeddings
```

## License

MIT
