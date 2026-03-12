"""AgentMemory — Persistent two-tier memory for AI agents."""

__version__ = "0.1.0"

from agentmemory.core.store import MemoryStore
from agentmemory.core.search import MemorySearch
from agentmemory.core.embeddings import cosine_similarity, get_embedding
from agentmemory.core.result import Result
from agentmemory.core.schema import ensure_schema, get_connection

__all__ = [
    "MemoryStore",
    "MemorySearch",
    "cosine_similarity",
    "get_embedding",
    "Result",
    "ensure_schema",
    "get_connection",
]

class DuplicateError(Exception):
    """Raised when a semantically duplicate entry is detected."""
    pass
