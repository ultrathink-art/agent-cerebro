"""Agent Cerebro — Persistent two-tier memory for AI agents."""

__version__ = "0.5.0"

from agentrecall.core.store import MemoryStore, DuplicateError
from agentrecall.core.search import MemorySearch
from agentrecall.core.embeddings import cosine_similarity, get_embedding
from agentrecall.core.result import Result
from agentrecall.core.schema import ensure_schema, get_connection
from agentrecall.core.timeline import MemoryTimeline
from agentrecall.core.export import MemoryExport
from agentrecall.core.stats import MemoryStats
from agentrecall.core.gc import MemoryGC
from agentrecall.core.lifecycle import (
    AlreadyInvalidatedError,
    EntryNotFoundError,
    MemoryLifecycle,
)

__all__ = [
    "MemoryStore",
    "MemorySearch",
    "MemoryTimeline",
    "MemoryExport",
    "MemoryStats",
    "MemoryGC",
    "MemoryLifecycle",
    "DuplicateError",
    "EntryNotFoundError",
    "AlreadyInvalidatedError",
    "cosine_similarity",
    "get_embedding",
    "Result",
    "ensure_schema",
    "get_connection",
]
