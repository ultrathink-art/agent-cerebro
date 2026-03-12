"""Uniform result type for memory operations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Result:
    """Uniform return type for all agentmemory operations."""

    text: Optional[str] = None
    created_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    similarity: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        status = "OK" if self.success else "FAILED"
        lines = [f"[{status}]"]
        if self.text:
            lines.append(f"  Text: {self.text}")
        if self.created_at:
            lines.append(f"  Created: {self.created_at}")
        if self.tags:
            lines.append(f"  Tags: {', '.join(self.tags)}")
        if self.similarity is not None:
            lines.append(f"  Similarity: {self.similarity:.4f}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        return "\n".join(lines)
