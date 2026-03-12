"""OpenAI embedding + cosine similarity. Pure Python, no numpy."""
from __future__ import annotations

import json
import math
import os
import struct
from typing import List, Optional

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two float vectors. Pure Python."""
    dot = 0.0
    mag_a = 0.0
    mag_b = 0.0
    for i in range(len(a)):
        dot += a[i] * b[i]
        mag_a += a[i] * a[i]
        mag_b += b[i] * b[i]
    mag_a = math.sqrt(mag_a)
    mag_b = math.sqrt(mag_b)
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def pack_embedding(embedding: List[float]) -> bytes:
    """Pack embedding as little-endian floats (binary blob for SQLite)."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


def unpack_embedding(blob: bytes) -> List[float]:
    """Unpack binary blob back to float list."""
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def get_api_key() -> Optional[str]:
    """Get OpenAI API key from environment."""
    return os.environ.get("UT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")


def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding via OpenAI text-embedding-3-small.

    Returns None if no API key is set.
    """
    api_key = get_api_key()
    if not api_key:
        return None

    import urllib.request

    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps({"model": EMBEDDING_MODEL, "input": text}).encode()

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            return body["data"][0]["embedding"]
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}")


def get_embeddings_batch(texts: List[str]) -> Optional[List[List[float]]]:
    """Batch embed multiple texts in one API call.

    Returns None if no API key is set.
    """
    api_key = get_api_key()
    if not api_key:
        return None

    import urllib.request

    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps({"model": EMBEDDING_MODEL, "input": texts}).encode()

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            sorted_data = sorted(body["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in sorted_data]
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}")
