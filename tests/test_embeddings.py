"""Tests for cosine similarity and embedding utilities."""
import math
import os
import struct

from agentmemory.core.embeddings import (
    cosine_similarity,
    get_api_key,
    pack_embedding,
    unpack_embedding,
    EMBEDDING_DIMS,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(vec, vec) - 1.0) < 0.0001

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b) - 0.0) < 0.0001

    def test_opposite_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [-1.0, -2.0, -3.0]
        assert abs(cosine_similarity(a, b) - (-1.0)) < 0.0001

    def test_zero_vectors(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors(self):
        a = [0.0, 0.0]
        b = [0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_similar_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        sim = cosine_similarity(a, b)
        assert sim > 0.99

    def test_large_vectors(self):
        a = [math.sin(i * 0.1) for i in range(EMBEDDING_DIMS)]
        b = [math.sin(i * 0.1) for i in range(EMBEDDING_DIMS)]
        assert abs(cosine_similarity(a, b) - 1.0) < 0.0001


class TestPackUnpack:
    def test_roundtrip(self):
        original = [1.0, 2.5, -3.7, 0.0, 100.0]
        packed = pack_embedding(original)
        unpacked = unpack_embedding(packed)
        for a, b in zip(original, unpacked):
            assert abs(a - b) < 0.0001

    def test_empty_vector(self):
        packed = pack_embedding([])
        unpacked = unpack_embedding(packed)
        assert unpacked == []

    def test_large_vector(self):
        original = [float(i) for i in range(EMBEDDING_DIMS)]
        packed = pack_embedding(original)
        assert len(packed) == EMBEDDING_DIMS * 4
        unpacked = unpack_embedding(packed)
        assert len(unpacked) == EMBEDDING_DIMS


class TestGetApiKey:
    def test_returns_none_without_key(self, monkeypatch):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert get_api_key() is None

    def test_prefers_ut_key(self, monkeypatch):
        monkeypatch.setenv("UT_OPENAI_API_KEY", "ut-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        assert get_api_key() == "ut-key"

    def test_falls_back_to_openai_key(self, monkeypatch):
        monkeypatch.delenv("UT_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        assert get_api_key() == "openai-key"
