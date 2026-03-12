# Agent Memory

Persistent two-tier memory for AI agents. Short-term markdown files (always loaded) + long-term SQLite with semantic search (queried on-demand).

## Setup

```bash
# Install (zero required deps — SQLite is stdlib)
pip install agentmemory

# Optional: enable semantic search/dedup
pip install agentmemory[embeddings]
export OPENAI_API_KEY="sk-..."

# Initialize memory directory
agentmemory init
```

## Quick Reference

### Store a memory
```bash
agentmemory store <role> <category> "text" --tags tag1,tag2
```

### Search memories
```bash
agentmemory search <role> <category> "query"
# Exit 0 = matches found, exit 1 = no matches
```

### List categories
```bash
agentmemory list <role>
```

### Check health
```bash
agentmemory check              # Short-term files
agentmemory check --long-term  # DB health
agentmemory check --all        # Both
agentmemory check --fix        # Auto-prune oversized files
```

## Protocol

1. **Session start**: Read `memory/<role>.md` — your accumulated knowledge
2. **Before acting**: `agentmemory search <role> <category> "concept"` to check past work
3. **After acting**: `agentmemory store <role> <category> "what you learned"`
4. **Session end**: Update `memory/<role>.md` with mistakes/learnings, run `agentmemory check`

## References

- [Memory Directive](references/memory-directive.md) — full agent protocol
- [Best Practices](references/best-practices.md) — patterns that work
- [Categories Guide](references/categories-guide.md) — suggested categories by role

## Scripts

- `scripts/store.py` — programmatic store
- `scripts/search.py` — programmatic search
- `scripts/check.py` — programmatic health check
- `scripts/setup.py` — initialize for a new project
