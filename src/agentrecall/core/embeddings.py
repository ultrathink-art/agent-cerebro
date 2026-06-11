"""OpenAI embedding + cosine similarity. Pure Python, no numpy.

Network calls to the OpenAI embeddings endpoint are wrapped in a retry loop
with exponential backoff + jitter. Transient failures (timeouts, dropped
connections, HTTP 429/5xx) are retried; on persistent failure the functions
degrade gracefully by returning ``None`` (and emitting a stderr warning)
instead of raising. Callers already treat ``None`` as "embeddings
unavailable" and fall back to keyword search / exact-text dedup, so a network
blip no longer hard-fails a command mid-session.
"""
from __future__ import annotations

import json
import math
import os
import random
import socket
import struct
import sys
import time
import urllib.error
import urllib.request
from typing import List, Optional

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

# Retry/backoff tuning. Overridable via env for flaky-network operators.
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
DEFAULT_BATCH_TIMEOUT = 60
RETRY_BASE_DELAY = 0.5
RETRY_MAX_DELAY = 8.0

# HTTP statuses worth retrying (transient server-side / rate limit).
RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

# Indirection so tests can stub sleeping without real delays.
_SLEEP = time.sleep


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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return default


def _max_retries() -> int:
    return _env_int("CEREBRO_EMBED_MAX_RETRIES", DEFAULT_MAX_RETRIES)


def _timeout(default: int) -> int:
    return _env_int("CEREBRO_EMBED_TIMEOUT", default)


def _warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def _retry_delay(attempt: int, http_error: Optional[urllib.error.HTTPError]) -> float:
    """Backoff delay for a given attempt (0-based), honoring Retry-After."""
    if http_error is not None and http_error.headers is not None:
        retry_after = http_error.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), RETRY_MAX_DELAY)
            except (ValueError, TypeError):
                pass
    delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
    # Full jitter on top of the base to avoid thundering-herd retries.
    return delay + random.uniform(0, delay * 0.25)


def _request_embeddings(payload: dict, api_key: str, timeout: int) -> Optional[dict]:
    """POST to the embeddings endpoint with retry/backoff.

    Returns the parsed JSON body on success, or ``None`` after exhausting
    retries / on a non-retryable error. Never raises for network or API
    failures — callers degrade gracefully on ``None``.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode()
    max_retries = _max_retries()

    attempt = 0
    while True:
        try:
            req = urllib.request.Request(
                OPENAI_EMBEDDINGS_URL, data=data, headers=headers
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            retryable = e.code in RETRYABLE_STATUS
            if not retryable or attempt >= max_retries:
                _warn(
                    f"OpenAI embedding request failed (HTTP {e.code}) "
                    f"after {attempt + 1} attempt(s): {e} — degrading to "
                    f"keyword/exact-match"
                )
                return None
            delay = _retry_delay(attempt, e)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            if attempt >= max_retries:
                _warn(
                    f"OpenAI embedding request failed (network) "
                    f"after {attempt + 1} attempt(s): {e} — degrading to "
                    f"keyword/exact-match"
                )
                return None
            delay = _retry_delay(attempt, None)
        except (json.JSONDecodeError, ValueError) as e:
            _warn(f"OpenAI embedding response was not valid JSON: {e}")
            return None

        _SLEEP(delay)
        attempt += 1


def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding via OpenAI text-embedding-3-small.

    Returns ``None`` if no API key is set, or if the API call fails after
    retries (graceful degradation — callers fall back to keyword search).
    """
    api_key = get_api_key()
    if not api_key:
        return None

    body = _request_embeddings(
        {"model": EMBEDDING_MODEL, "input": text}, api_key, _timeout(DEFAULT_TIMEOUT)
    )
    if body is None:
        return None
    try:
        return body["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as e:
        _warn(f"Unexpected OpenAI embedding response shape: {e}")
        return None


def get_embeddings_batch(texts: List[str]) -> Optional[List[List[float]]]:
    """Batch embed multiple texts in one API call.

    Returns ``None`` if no API key is set, or if the API call fails after
    retries (graceful degradation).
    """
    api_key = get_api_key()
    if not api_key:
        return None

    body = _request_embeddings(
        {"model": EMBEDDING_MODEL, "input": texts}, api_key, _timeout(DEFAULT_BATCH_TIMEOUT)
    )
    if body is None:
        return None
    try:
        sorted_data = sorted(body["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in sorted_data]
    except (KeyError, IndexError, TypeError) as e:
        _warn(f"Unexpected OpenAI embedding response shape: {e}")
        return None
