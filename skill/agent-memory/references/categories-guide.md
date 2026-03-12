# Suggested Categories by Role

Any agent can create categories by storing the first entry. Convention: `snake_case`.

| Role | Category | Use |
|------|----------|-----|
| social | `exhausted_stories` | Topics/stories already posted |
| social | `engagement_patterns` | What works on each platform |
| designer | `rejected_designs` | Concepts rejected and why |
| designer | `successful_designs` | What sold well and patterns |
| coder | `fix_attempts` | Past debugging approaches per bug class |
| coder | `gotchas` | Non-obvious platform/framework traps |
| qa | `defect_patterns` | Historical defect catalog |
| operations | `audit_findings` | Systemic issues found and fixes applied |
| marketing | `published_topics` | Blog/content topics already covered |
| marketing | `content_performance` | What content drove traffic |
| security | `vulnerability_patterns` | Recurring vuln types across audits |
| product | `launch_history` | Products launched and outcomes |

## Creating New Categories

Just store an entry — the category is created implicitly:

```bash
agentmemory store myagent new_category "first entry in this category"
```

## Category Size Guidelines

- **< 10 entries**: Category may be too narrow, consider merging
- **10-50 entries**: Ideal range for focused, searchable memory
- **50-200 entries**: Still fine — semantic search handles it well
- **200+ entries**: Consider splitting into subcategories
