"""Shared fixtures for agentmemory tests."""
import math
import os
import sqlite3
import tempfile

import pytest

from agentmemory.core.schema import ensure_schema
from agentmemory.core.embeddings import EMBEDDING_DIMS


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database with schema."""
    db_path = str(tmp_path / "test_memory.sqlite3")
    conn = sqlite3.connect(db_path)
    ensure_schema(conn)
    conn.close()
    return db_path


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    d = tmp_path / "memory"
    d.mkdir()
    return str(d)


def fake_embedding(seed=0.1):
    """Generate a deterministic fake embedding vector."""
    return [math.sin(i * seed) for i in range(EMBEDDING_DIMS)]


def make_embed_fn(seed=0.1):
    """Create an embed function that returns a fixed vector."""
    emb = fake_embedding(seed)
    return lambda text: emb


def null_embed_fn(text):
    """Embed function that returns None (simulates no API key)."""
    return None
