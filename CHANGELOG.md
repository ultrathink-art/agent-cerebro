# Changelog

## 0.1.0 (2026-03-11)

Initial release.

- Two-tier memory: short-term markdown files + long-term SQLite with OpenAI embeddings
- CLI: `agentmemory store/search/list/check/init/migrate`
- Semantic dedup via cosine similarity (threshold >0.92)
- Keyword fallback when no OpenAI API key
- Short-term memory file validation (80-line limit, session log pruning)
- JSONL to SQLite migration tool
- Agent Skills packaging (`skill/agent-memory/`)
- Zero required dependencies (SQLite is stdlib)
- Full pytest suite
