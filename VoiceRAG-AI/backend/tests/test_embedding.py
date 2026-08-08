"""
Unit tests for the embedding pipeline.

All tests mock the Gemini client so no real API key or network call is needed.
Tests cover:
  - EmbeddingCache (L1 memory + L2 disk)
  - EmbeddingService: cache hit/miss paths, batching, retry, progress tracking
  - _partition and _jittered_backoff helpers
  - EmbeddingService.embed_text convenience method
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.cache import EmbeddingCache
from app.models.chunk import ChunkMetadata, DocumentChunk
from app.models.embedding import (
    CachedEmbedding,
    EmbeddingBatchResult,
    EmbeddingProgress,
    EmbeddingRecord,
)
from app.services.embedding_service import (
    EmbeddingService,
    _is_retryable,
    _jittered_backoff,
    _partition,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_FAKE_VECTOR: list[float] = [0.1, 0.2, 0.3]
_MODEL = "text-embedding-004"
_DOC_ID = "test-doc-uuid"


def _make_chunk(chunk_id: str, text: str = "hello world") -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        chunk_index=0,
        text=text,
        metadata=ChunkMetadata(
            document_id=_DOC_ID,
            original_filename="test.pdf",
            page_number=1,
            total_pages=1,
        ),
    )


def _make_chunks(n: int) -> list[DocumentChunk]:
    return [_make_chunk(f"chunk_{i}", f"text content number {i}") for i in range(n)]


def _fake_embed_response(n: int) -> MagicMock:
    """Build a mock Gemini embed_content response with *n* embeddings."""
    resp = MagicMock()
    embeddings = []
    for _ in range(n):
        emb = MagicMock()
        emb.values = _FAKE_VECTOR
        embeddings.append(emb)
    resp.embeddings = embeddings
    return resp


@pytest.fixture()
def tmp_cache(tmp_path: Path) -> EmbeddingCache:
    return EmbeddingCache(cache_dir=tmp_path / "cache", max_memory_entries=4)


@pytest.fixture()
def service(tmp_path: Path) -> EmbeddingService:
    """EmbeddingService with injected cache and no-op Gemini key."""
    cache = EmbeddingCache(cache_dir=tmp_path / "emb_cache", max_memory_entries=16)
    svc = EmbeddingService(
        api_key="fake-key",
        model=_MODEL,
        batch_size=3,
        max_concurrent=2,
        max_retries=2,
        retry_base_secs=0.01,  # fast in tests
        cache=cache,
    )
    return svc


# ---------------------------------------------------------------------------
# EmbeddingCache tests
# ---------------------------------------------------------------------------


class TestEmbeddingCache:
    async def test_miss_returns_none(self, tmp_cache: EmbeddingCache) -> None:
        result = await tmp_cache.get("unknown text")
        assert result is None

    async def test_put_then_get_memory(self, tmp_cache: EmbeddingCache) -> None:
        await tmp_cache.put("hello", "c1", _FAKE_VECTOR, _MODEL)
        hit = await tmp_cache.get("hello")
        assert hit is not None
        assert hit.vector == _FAKE_VECTOR
        assert hit.model == _MODEL

    async def test_disk_persistence(self, tmp_path: Path) -> None:
        """Entry survives creating a brand-new cache instance (L2 hit)."""
        cache1 = EmbeddingCache(cache_dir=tmp_path / "c", max_memory_entries=4)
        await cache1.put("persist me", "c2", _FAKE_VECTOR, _MODEL)

        cache2 = EmbeddingCache(cache_dir=tmp_path / "c", max_memory_entries=4)
        hit = await cache2.get("persist me")
        assert hit is not None
        assert hit.vector == _FAKE_VECTOR

    async def test_text_hash_is_deterministic(self, tmp_cache: EmbeddingCache) -> None:
        h1 = EmbeddingCache.text_hash("same text")
        h2 = EmbeddingCache.text_hash("same text")
        assert h1 == h2

    async def test_lru_eviction(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "lru", max_memory_entries=2)
        await cache.put("a", "c1", _FAKE_VECTOR, _MODEL)
        await cache.put("b", "c2", _FAKE_VECTOR, _MODEL)
        await cache.put("c", "c3", _FAKE_VECTOR, _MODEL)  # evicts "a" from L1
        assert cache.memory_size == 2

    async def test_invalidate_removes_from_memory_and_disk(
        self, tmp_cache: EmbeddingCache
    ) -> None:
        await tmp_cache.put("bye", "c1", _FAKE_VECTOR, _MODEL)
        await tmp_cache.invalidate("bye")
        hit = await tmp_cache.get("bye")
        assert hit is None

    async def test_clear_wipes_all(self, tmp_cache: EmbeddingCache) -> None:
        await tmp_cache.put("x", "c1", _FAKE_VECTOR, _MODEL)
        await tmp_cache.put("y", "c2", _FAKE_VECTOR, _MODEL)
        await tmp_cache.clear()
        assert tmp_cache.memory_size == 0
        assert await tmp_cache.get("x") is None


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestPartition:
    def test_exact_multiple(self) -> None:
        chunks = _make_chunks(6)
        batches = _partition(chunks, 3)
        assert len(batches) == 2
        assert all(len(b) == 3 for b in batches)

    def test_remainder_batch(self) -> None:
        chunks = _make_chunks(7)
        batches = _partition(chunks, 3)
        assert len(batches) == 3
        assert len(batches[-1]) == 1

    def test_single_item(self) -> None:
        chunks = _make_chunks(1)
        batches = _partition(chunks, 10)
        assert len(batches) == 1

    def test_empty(self) -> None:
        assert _partition([], 5) == []

    def test_invalid_size_raises(self) -> None:
        with pytest.raises(ValueError):
            _partition(_make_chunks(3), 0)


class TestJitteredBackoff:
    def test_returns_float_in_range(self) -> None:
        for attempt in range(5):
            delay = _jittered_backoff(attempt, base=1.0)
            assert 0.0 <= delay <= 1.0 * (2**attempt)

    def test_non_negative(self) -> None:
        for _ in range(20):
            assert _jittered_backoff(0, 1.0) >= 0


class TestIsRetryable:
    def test_429_keyword(self) -> None:
        assert _is_retryable(Exception("got 429 rate limit"))

    def test_quota_keyword(self) -> None:
        assert _is_retryable(Exception("quota exceeded"))

    def test_503_keyword(self) -> None:
        assert _is_retryable(Exception("503 service unavailable"))

    def test_status_code_attr(self) -> None:
        exc = Exception("oops")
        exc.status_code = 503  # type: ignore[attr-defined]
        assert _is_retryable(exc)

    def test_non_retryable(self) -> None:
        assert not _is_retryable(ValueError("bad input"))

    def test_404_not_retryable(self) -> None:
        exc = Exception("not found")
        exc.status_code = 404  # type: ignore[attr-defined]
        assert not _is_retryable(exc)


# ---------------------------------------------------------------------------
# EmbeddingService tests
# ---------------------------------------------------------------------------


class TestEmbeddingServiceEmpty:
    async def test_empty_chunks_returns_zero_result(
        self, service: EmbeddingService
    ) -> None:
        result = await service.embed_chunks(_DOC_ID, [])
        assert isinstance(result, EmbeddingBatchResult)
        assert result.total == 0
        assert result.succeeded == 0
        assert result.embeddings == []


class TestEmbeddingServiceCacheHit:
    async def test_all_cache_hits_no_api_call(self, service: EmbeddingService) -> None:
        chunks = _make_chunks(2)
        # Pre-populate cache for both chunks
        for chunk in chunks:
            await service._cache.put(chunk.text, chunk.chunk_id, _FAKE_VECTOR, _MODEL)

        with patch.object(service, "_call_api_batch", new_callable=AsyncMock) as mock_api:
            result = await service.embed_chunks(_DOC_ID, chunks)

        mock_api.assert_not_called()
        assert result.cache_hits == 2
        assert result.succeeded == 2
        assert result.failed == 0

    async def test_partial_cache_hit(self, service: EmbeddingService) -> None:
        chunks = _make_chunks(4)
        # Cache only the first 2
        for chunk in chunks[:2]:
            await service._cache.put(chunk.text, chunk.chunk_id, _FAKE_VECTOR, _MODEL)

        with patch.object(
            service,
            "_call_api_batch",
            new_callable=AsyncMock,
            return_value=[
                EmbeddingRecord(
                    chunk_id=chunks[2].chunk_id,
                    vector=_FAKE_VECTOR,
                    model=_MODEL,
                    cached=False,
                    created_at=datetime.now(timezone.utc),
                ),
                EmbeddingRecord(
                    chunk_id=chunks[3].chunk_id,
                    vector=_FAKE_VECTOR,
                    model=_MODEL,
                    cached=False,
                    created_at=datetime.now(timezone.utc),
                ),
            ],
        ):
            result = await service.embed_chunks(_DOC_ID, chunks)

        assert result.cache_hits == 2
        assert result.succeeded == 4
        assert result.failed == 0


class TestEmbeddingServiceAPICall:
    async def test_successful_batch_embedding(self, service: EmbeddingService) -> None:
        chunks = _make_chunks(5)  # will be split into batches of 3 + 2
        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(
            side_effect=lambda model, contents: _fake_embed_response(len(contents))
        )
        service._client = fake_client

        result = await service.embed_chunks(_DOC_ID, chunks)

        assert result.total == 5
        assert result.succeeded == 5
        assert result.failed == 0
        assert len(result.embeddings) == 5
        assert all(r.vector == _FAKE_VECTOR for r in result.embeddings)

    async def test_embedding_records_have_correct_chunk_ids(
        self, service: EmbeddingService
    ) -> None:
        chunks = _make_chunks(3)
        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(
            side_effect=lambda model, contents: _fake_embed_response(len(contents))
        )
        service._client = fake_client

        result = await service.embed_chunks(_DOC_ID, chunks)
        result_ids = {r.chunk_id for r in result.embeddings}
        expected_ids = {c.chunk_id for c in chunks}
        assert result_ids == expected_ids

    async def test_cached_false_for_api_results(self, service: EmbeddingService) -> None:
        chunks = _make_chunks(2)
        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(
            side_effect=lambda model, contents: _fake_embed_response(len(contents))
        )
        service._client = fake_client

        result = await service.embed_chunks(_DOC_ID, chunks)
        for rec in result.embeddings:
            assert rec.cached is False


class TestEmbeddingServiceRetry:
    async def test_retries_on_transient_error(self, service: EmbeddingService) -> None:
        chunks = _make_chunks(2)
        call_count = 0

        async def flaky_api(model: str, contents: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 rate limit")
            return _fake_embed_response(len(contents))

        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(side_effect=flaky_api)
        service._client = fake_client

        result = await service.embed_chunks(_DOC_ID, chunks)
        assert result.succeeded == 2
        assert call_count == 3  # 2 failures + 1 success

    async def test_exhausted_retries_records_failure(
        self, service: EmbeddingService
    ) -> None:
        service._max_retries = 1
        chunks = _make_chunks(2)

        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(
            side_effect=Exception("503 unavailable")
        )
        service._client = fake_client

        result = await service.embed_chunks(_DOC_ID, chunks)
        assert result.failed == 2
        assert result.succeeded == 0

    async def test_non_retryable_error_no_retry(self, service: EmbeddingService) -> None:
        chunks = _make_chunks(1)
        call_count = 0

        async def non_retryable(model: str, contents: Any) -> Any:
            nonlocal call_count
            call_count += 1
            raise ValueError("validation error — not retryable")

        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(side_effect=non_retryable)
        service._client = fake_client

        result = await service.embed_chunks(_DOC_ID, chunks)
        assert result.failed == 1
        assert call_count == 1  # no retry for non-retryable


class TestProgressTracking:
    async def test_progress_callback_called_per_batch(
        self, service: EmbeddingService
    ) -> None:
        """Progress callback should be called once per batch (not per chunk)."""
        chunks = _make_chunks(7)  # batch_size=3 → 3 batches
        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(
            side_effect=lambda model, contents: _fake_embed_response(len(contents))
        )
        service._client = fake_client

        progress_snapshots: list[EmbeddingProgress] = []

        async def on_progress(p: EmbeddingProgress) -> None:
            progress_snapshots.append(p)

        await service.embed_chunks(_DOC_ID, chunks, on_progress=on_progress)

        # 3 batches → 3 progress snapshots
        assert len(progress_snapshots) == 3
        # Final snapshot: all processed
        final = progress_snapshots[-1]
        assert final.total == 7
        assert final.document_id == _DOC_ID

    async def test_progress_percent(self, service: EmbeddingService) -> None:
        p = EmbeddingProgress(
            document_id=_DOC_ID, processed=50, total=100, cache_hits=0, failed=0
        )
        assert p.percent == 50.0

    async def test_progress_percent_zero_total(self) -> None:
        p = EmbeddingProgress(
            document_id=_DOC_ID, processed=0, total=0, cache_hits=0, failed=0
        )
        assert p.percent == 0.0

    async def test_sync_callback_accepted(self, service: EmbeddingService) -> None:
        """A synchronous callback (non-coroutine) must not raise."""
        chunks = _make_chunks(3)
        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(
            side_effect=lambda model, contents: _fake_embed_response(len(contents))
        )
        service._client = fake_client

        called: list[int] = []

        def sync_callback(p: EmbeddingProgress) -> None:
            called.append(p.processed)

        result = await service.embed_chunks(_DOC_ID, chunks, on_progress=sync_callback)
        assert result.succeeded == 3
        assert len(called) == 1  # one batch for 3 chunks at batch_size=3


class TestEmbedText:
    async def test_embed_text_cache_miss(self, service: EmbeddingService) -> None:
        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock(
            return_value=_fake_embed_response(1)
        )
        service._client = fake_client

        vector = await service.embed_text("query text")
        assert vector == _FAKE_VECTOR

    async def test_embed_text_cache_hit(self, service: EmbeddingService) -> None:
        await service._cache.put("query text", "_q_", _FAKE_VECTOR, _MODEL)
        fake_client = MagicMock()
        fake_client.aio.models.embed_content = AsyncMock()
        service._client = fake_client

        vector = await service.embed_text("query text")
        fake_client.aio.models.embed_content.assert_not_called()
        assert vector == _FAKE_VECTOR


class TestMissingAPIKey:
    async def test_raises_service_error_without_key(self, tmp_path: Path) -> None:
        from app.core.exceptions import ServiceError

        cache = EmbeddingCache(cache_dir=tmp_path / "c")
        svc = EmbeddingService(api_key="", model=_MODEL, cache=cache)

        with pytest.raises(ServiceError, match="GEMINI_API_KEY"):
            svc._get_client()
