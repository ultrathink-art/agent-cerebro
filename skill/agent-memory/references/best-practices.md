# Memory Best Practices

## Short-Term (markdown files)

- **Be specific**: "Run `CI=true bin/rails test` after commit" > "Don't forget tests"
- **Be honest**: Record mistakes — your memory is working notes, not a performance review
- **Prune actively**: Every update, scan for stale/duplicate entries and remove them
- **Don't duplicate docs**: If a rule exists in project docs, reference it, don't copy
- **Newest first**: Append at TOP of each section so the most relevant info is seen first

## Long-Term (SQLite + embeddings)

- **Search before acting**: Always check if you've done similar work before
- **Store after acting**: Record what you did so future sessions can find it
- **Use tags**: Tags expand searchability (`--tags deploy,sqlite,orders`)
- **Let dedup work**: If store rejects as duplicate, that's correct behavior — don't force it
- **Category naming**: Use `snake_case`. Keep categories focused (10-50 entries ideal)

## Two-Tier Design

| When to use short-term | When to use long-term |
|---|---|
| Active lessons you need every session | Growing lists (exhausted topics, known entities) |
| Recent mistakes to avoid | Historical catalog (past designs, past bugs) |
| Stakeholder preferences | Reference data searched on-demand |

## Anti-Patterns

- **Append-only logs**: Memory files that only grow → use long-term storage instead
- **Copying project docs**: Wastes your 80-line budget on info that exists elsewhere
- **Vague entries**: "Be careful with deploys" teaches nothing
- **Stale entries**: Bugs that were fixed, tools that changed → delete them
- **Duplicate lessons**: Same lesson recorded 3+ times means you're not learning from it
