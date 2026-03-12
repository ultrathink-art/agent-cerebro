# Agent Memory Protocol

You have persistent memory across sessions. USE IT.

## At Session START

Read your memory file: `memory/<your-role>.md`

Contains accumulated knowledge — mistakes, learnings, feedback, session log. Treat as your personal notebook.

## At Session END

Update your memory file. Add entries to relevant sections. Be specific and actionable.

Run `agentmemory check` to validate size limits. Use `agentmemory check --fix` if over limit.

### What to record

**Mistakes** — what went wrong, correct approach, how to avoid next time.

**Learnings** — non-obvious discoveries, gotchas, workarounds, patterns that work.

**Session Log** — 1-2 lines per session: task ID, what you worked on, outcome.

### Format

Append new entries at TOP of each section (newest first). Date prefix: `[YYYY-MM-DD]`.

### Size limits

- Mistakes: max 20 entries
- Learnings: max 20 entries
- Session Log: max 15 entries
- Total file: max 80 lines

### Pruning rules

- Remove entries duplicated in project instructions
- Remove stale entries (fixed bugs, removed workarounds)
- Consolidate duplicate lessons into one entry
- Use long-term memory (`agentmemory store`) for growing lists

## Long-Term Memory

For data that grows unboundedly (exhausted topics, known patterns, recurring references).

### Search-before-action pattern

```bash
# Before creating content that might duplicate past work:
agentmemory search <role> <category> "<concept keywords>"
# Exit 0 = matches found → skip/choose different topic
# Exit 1 = no matches → safe to proceed

# After completing work:
agentmemory store <role> <category> "<what you did>"
```

## Memory File Template

```markdown
# {Role} Agent Memory

## Mistakes
- [2026-03-11] Description of what went wrong and how to avoid it.

## Learnings
- [2026-03-11] Non-obvious discovery specific to your role.

## Session Log
- [2026-03-11] Task/summary of what was done.
```
