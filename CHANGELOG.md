# Changelog

## 0.5.0 (2026-08-07)

Memory lifecycle support, driven by a dogfood incident where a known-unsafe
long-term entry remained searchable and agents had to maintain a separate advisory
denylist because Cerebro could neither invalidate nor supersede it.

- **Addressable search and timeline** — opt-in `--show-id` output exposes stable
  entry IDs without changing the default CLI output. The Python API keeps
  `MemorySearch.search()` compatible as `list[str]` and adds `search_records()`.
- **Soft invalidation** — `cerebro invalidate <id> --reason "..."` removes stale
  beliefs from normal search, dedup, counts, timeline, export, and GC while keeping
  the historical row auditable. Timeline and export add an explicit
  `--include-invalidated` audit mode with timestamp and reason metadata.
- **Atomic supersession** — `cerebro supersede <id> "replacement"` inserts the
  correction in the original role/category, preserves or replaces tags, and links
  the invalidated original through `superseded_by`, all in one SQLite transaction.
  The target itself is exempted from duplicate detection; other active duplicates
  still block the transition.
- **Automatic 0.4.x migration** — existing SQLite databases gain the three lifecycle
  columns and active-entry index in place. Existing rows and IDs are preserved.

17 new tests (214 total), including a literal 0.4.x database migration fixture,
transaction rollback, installed CLI behavior, and Python API compatibility.

## 0.4.1 (2026-06-12)

Docs-only release.

- README: added Newsletter section (stdout — running AI agents in production).
- No functional changes.

## 0.4.0 (2026-06-11)

Network resilience + output control, driven by dogfooding our own agents.

- **Retry + graceful degradation on embedding calls** — the OpenAI embedding
  request now retries transient failures (timeouts, dropped connections, HTTP
  429/5xx) with exponential backoff + jitter, honoring `Retry-After` on 429.
  After exhausting retries — or on a non-retryable error like 401 — `store` and
  `search` print a warning and fall back to keyword/exact-match instead of
  raising. Previously a single network blip hard-failed the command mid-session.
- **Tunable resilience** — `CEREBRO_EMBED_MAX_RETRIES` (default 3) and
  `CEREBRO_EMBED_TIMEOUT` (default 30s) environment variables.
- **`cerebro search --limit N`** — cap results to the top-N by relevance, to keep
  agent context windows tight on large categories.
- **Accurate degradation warning** — search no longer claims "No OpenAI API key"
  when the real cause is a network failure; it now says "embeddings unavailable".

`get_embedding` / `get_embeddings_batch` now return `None` on persistent failure
(matching their existing no-API-key contract) rather than raising `RuntimeError`.

23 new tests (197 total).

## 0.3.0 (2026-03-27)

Five new features for memory management at scale:

- **Timeline** — chronological view of memories: `cerebro timeline [role] [--last 7d] [--category cat]`
- **Export** — dump memories as markdown or JSON: `cerebro export [role] --format md|json`
- **Stats** — storage metrics, embedding coverage, category breakdown: `cerebro stats [role]`
- **Garbage collection** — find and remove near-duplicate entries: `cerebro gc [role] --dry-run|--apply`
- **Tag filtering on search** — narrow search results by tag: `cerebro search role cat query --tag important`

New Python API classes: `MemoryTimeline`, `MemoryExport`, `MemoryStats`, `MemoryGC`.

66 new tests (174 total).

## 0.2.0 (2026-03-12)

Complete rebrand from AgentRecall to Agent Cerebro.

- CLI command: `cerebro` (plus `agentrecall`, `agentmemory` aliases)
- Environment variable: `AGENT_CEREBRO_HOME` (with `AGENT_RECALL_HOME` fallback)
- Default storage: `~/.agent-cerebro/`

## 0.1.2 (2026-03-12)

Renamed PyPI package from `agentrecall-memory` to `agent-cerebro` (v0.1.0). Python import name (`from agentrecall import ...`) and CLI commands (`agentrecall`/`cerebro`) are unchanged.

## 0.1.1 (2026-03-12)

Renamed PyPI package from `agentrecall` to `agentrecall-memory` (PyPI rejected `agentrecall` as too similar to existing `agent-recall`). Python import name (`from agentrecall import ...`) and CLI commands (`agentrecall store/search/...`) are unchanged.

## 0.1.0 (2026-03-11)

Initial release (as agentrecall, renamed from agentmemory).

- Two-tier memory: short-term markdown files + long-term SQLite with OpenAI embeddings
- CLI: `agentrecall store/search/list/check/init/migrate`
- Semantic dedup via cosine similarity (threshold >0.92)
- Keyword fallback when no OpenAI API key
- Short-term memory file validation (80-line limit, session log pruning)
- JSONL to SQLite migration tool
- Agent Skills packaging (`skill/agent-recall/`)
- Zero required dependencies (SQLite is stdlib)
- Full pytest suite
