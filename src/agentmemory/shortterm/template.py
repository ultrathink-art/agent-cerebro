"""Generate memory file templates for new agent roles."""
from __future__ import annotations

TEMPLATE = """# {role} Agent Memory

## Mistakes
<!-- Append new entries at TOP (newest first). Format: - [YYYY-MM-DD] Description -->

## Learnings
<!-- Append new entries at TOP (newest first). Format: - [YYYY-MM-DD] Description -->

## Shareholder Feedback
<!-- Keep ALL entries. Never prune. -->

## Session Log
<!-- Max 15 sessions. Prune oldest when over 15. Format: - [YYYY-MM-DD] Task/summary -->
"""


def generate_template(role: str) -> str:
    """Generate a memory file template for a given role."""
    return TEMPLATE.format(role=role.capitalize())
