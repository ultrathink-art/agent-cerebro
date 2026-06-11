"""Tests for retry/backoff + graceful degradation on the embedding call."""
import json
import urllib.error

import pytest

from agentrecall.core import embeddings


class FakeResponse:
    """Minimal context-manager stand-in for urlopen()'s return value."""

    def __init__(self, body: dict):
        self._body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _ok_body(dims=3):
    return {"data": [{"index": 0, "embedding": [0.1] * dims}]}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Never actually sleep during retry tests."""
    monkeypatch.setattr(embeddings, "_SLEEP", lambda _s: None)


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRO_EMBED_MAX_RETRIES", raising=False)


def _patch_urlopen(monkeypatch, side_effects):
    """side_effects: list of either FakeResponse or Exception instances."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        idx = calls["n"]
        calls["n"] += 1
        effect = side_effects[min(idx, len(side_effects) - 1)]
        if isinstance(effect, Exception):
            raise effect
        return effect

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


class TestRetry:
    def test_succeeds_first_try(self, monkeypatch):
        calls = _patch_urlopen(monkeypatch, [FakeResponse(_ok_body())])
        result = embeddings.get_embedding("hello")
        assert result == [0.1, 0.1, 0.1]
        assert calls["n"] == 1

    def test_retries_transient_5xx_then_succeeds(self, monkeypatch):
        err = urllib.error.HTTPError("u", 503, "unavailable", {}, None)
        calls = _patch_urlopen(monkeypatch, [err, err, FakeResponse(_ok_body())])
        result = embeddings.get_embedding("hello")
        assert result == [0.1, 0.1, 0.1]
        assert calls["n"] == 3

    def test_retries_network_error_then_succeeds(self, monkeypatch):
        err = urllib.error.URLError("connection reset")
        calls = _patch_urlopen(monkeypatch, [err, FakeResponse(_ok_body())])
        result = embeddings.get_embedding("hello")
        assert result == [0.1, 0.1, 0.1]
        assert calls["n"] == 2

    def test_degrades_to_none_after_exhausting_retries(self, monkeypatch):
        err = urllib.error.URLError("network down")
        calls = _patch_urlopen(monkeypatch, [err])
        result = embeddings.get_embedding("hello")
        assert result is None
        # 1 initial + DEFAULT_MAX_RETRIES retries
        assert calls["n"] == embeddings.DEFAULT_MAX_RETRIES + 1

    def test_non_retryable_4xx_returns_none_without_retry(self, monkeypatch):
        err = urllib.error.HTTPError("u", 401, "unauthorized", {}, None)
        calls = _patch_urlopen(monkeypatch, [err])
        result = embeddings.get_embedding("hello")
        assert result is None
        assert calls["n"] == 1  # no retries on auth error

    def test_max_retries_env_override(self, monkeypatch):
        monkeypatch.setenv("CEREBRO_EMBED_MAX_RETRIES", "1")
        err = urllib.error.HTTPError("u", 500, "err", {}, None)
        calls = _patch_urlopen(monkeypatch, [err])
        result = embeddings.get_embedding("hello")
        assert result is None
        assert calls["n"] == 2  # 1 initial + 1 retry

    def test_no_api_key_returns_none_no_call(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        calls = _patch_urlopen(monkeypatch, [FakeResponse(_ok_body())])
        assert embeddings.get_embedding("hi") is None
        assert calls["n"] == 0

    def test_malformed_json_returns_none(self, monkeypatch):
        class BadResponse(FakeResponse):
            def read(self):
                return b"<html>not json</html>"

        _patch_urlopen(monkeypatch, [BadResponse({})])
        assert embeddings.get_embedding("hi") is None

    def test_batch_degrades_to_none(self, monkeypatch):
        err = urllib.error.URLError("down")
        _patch_urlopen(monkeypatch, [err])
        assert embeddings.get_embeddings_batch(["a", "b"]) is None

    def test_batch_succeeds(self, monkeypatch):
        body = {"data": [
            {"index": 1, "embedding": [0.2]},
            {"index": 0, "embedding": [0.1]},
        ]}
        _patch_urlopen(monkeypatch, [FakeResponse(body)])
        result = embeddings.get_embeddings_batch(["a", "b"])
        assert result == [[0.1], [0.2]]  # sorted by index


class TestRetryDelay:
    def test_honors_retry_after_header(self):
        err = urllib.error.HTTPError("u", 429, "rate limited", {"Retry-After": "2"}, None)
        delay = embeddings._retry_delay(0, err)
        assert delay == 2.0

    def test_backoff_grows_with_attempt(self):
        d0 = embeddings._retry_delay(0, None)
        d2 = embeddings._retry_delay(2, None)
        assert d2 > d0

    def test_delay_capped(self):
        delay = embeddings._retry_delay(20, None)
        assert delay <= embeddings.RETRY_MAX_DELAY * 1.25
