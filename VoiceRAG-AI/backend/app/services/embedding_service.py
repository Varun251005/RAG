"""
Embedding service — converts ``DocumentChunk`` objects into float vectors
using the Gemini Embedding API (``google-genai`` SDK).

Features
--------
* **Batching** — chunks are grouped into batches of ``batch_size`` and sent
  as concurrent API calls capped by a ``max_concurrent`` semaphore to avoid
  overwhelming the API quota.
* **Retry with exponential back-off** — each individual API call retries up
  to ``max_retries`` times with jittered delays on transient errors
  (rate-limit 429 and server 5xx).
* **Progress tracking** — an optional async callback receives an
  ``EmbeddingProgress`` snapshot after every batch so callers can drive
  progress bars, streaming SSE responses, or structured logs.
* **Two-tier cache** — ``EmbeddingCache`` (memory LRU + atomic disk JSON)
  is checked before every API call; hits bypass the network entirely.
* **No retrieval** — this service only *produces* vectors; storage and
  similarity search are handled downstream.

Usage
-----
    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    result = await service.embed_chunks(
        document_id="doc-uuid",
        chunks=chunking_result.chunks,
        on_progress=lambda p: print(f"{p.percent:.0f}%"),
    )
    for rec in result.embeddings:
        print(rec.chunk_id, len(rec.vector))

Configuration (``app.core.config.Settings``)
--------------------------------------------
    GEMINI_API_KEY            — required; Gemini API key.
    GEMINI_EMBEDDING_MODEL    — model name (default: text-embedding-004).
    EMBEDDING_BATCH_SIZE      — chunks per API call (default: 100).
    EMBEDDING_MAX_CONCURRENT  — concurrent API calls (default: 5).
    EMBEDDING_MAX_RETRIES     — per-call retry attempts (default: 3).
    EMBEDDING_RETRY_BASE_SECS — base back-off in seconds (default: 1.0).
    EMBEDDING_CACHE_DIR       — disk cache directory (default: .embedding_cache).
    EMBEDDING_CACHE_MAX_MEM   — L1 memory cache entries (default: 2048).
"""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import types as genai_types
from loguru import logger

from app.core.cache import EmbeddingCache
from app.core.config import get_settings
from app.core.exceptions import ServiceError
from app.models.chunk import DocumentChunk
from app.models.embedding import (
    EmbeddingBatchResult,
    EmbeddingRecord,
    EmbeddingProgress,
    EmbeddingVector,
)

# Type alias for the optional progress callback.
ProgressCallback = Callable[[EmbeddingProgress], Coroutine[Any, Any, None] | None]

# HTTP-level error codes treated as transient (worth retrying).
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class EmbeddingService:
    """
    Production-grade async embedding service backed by Gemini.

    Parameters
    ----------
    api_key :
        Gemini API key.  Defaults to ``Settings.gemini_api_key``.
    model :
        Gemini embedding model name.  Defaults to ``Settings.gemini_embedding_model``.
    batch_size :
        Number of chunks sent per API call.
    max_concurrent :
        Maximum number of concurrent API calls in flight.
    max_retries :
        Per-call retry attempts on transient errors.
    retry_base_secs :
        Exponential back-off base (seconds); jitter is added automatically.
    cache :
        Optional pre-built :class:`EmbeddingCache` instance.  If ``None`` a
        default instance is constructed from Settings.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        batch_size: int | None = None,
        max_concurrent: int | None = None,
        max_retries: int | None = None,
        retry_base_secs: float | None = None,
        cache: EmbeddingCache | None = None,
    ) -> None:
        cfg = get_settings()

        self._api_key: str = api_key if api_key is not None else cfg.gemini_api_key
        self._model: str = model or cfg.gemini_embedding_model
        self._batch_size: int = batch_size or cfg.embedding_batch_size
        self._max_concurrent: int = max_concurrent or cfg.embedding_max_concurrent
        self._max_retries: int = max_retries if max_retries is not None else cfg.embedding_max_retries
        self._retry_base: float = retry_base_secs if retry_base_secs is not None else cfg.embedding_retry_base_secs

        # Semaphore gates concurrent outbound API calls.
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

        # Cache (injected or constructed from settings).
        from pathlib import Path

        self._cache: EmbeddingCache = cache or EmbeddingCache(
            cache_dir=Path(cfg.embedding_cache_dir),
            max_memory_entries=cfg.embedding_cache_max_mem,
        )

        # Lazy Gemini client — created once on first use.
        self._client: genai.Client | None = None

        logger.debug(
            f"EmbeddingService initialised | model={self._model} | "
            f"batch_size={self._batch_size} | max_concurrent={self._max_concurrent} | "
            f"max_retries={self._max_retries}"
        )

    # ── Public interface ───────────────────────────────────────────────────────

    async def embed_chunks(
        self,
        document_id: str,
        chunks: list[DocumentChunk],
        on_progress: ProgressCallback | None = None,
    ) -> EmbeddingBatchResult:
        """
        Embed *chunks* and return an :class:`EmbeddingBatchResult`.

        Steps
        -----
        1. Resolve cache hits without touching the network.
        2. Partition remaining chunks into batches of ``batch_size``.
        3. Dispatch batches concurrently (bounded by ``max_concurrent``).
        4. Retry each batch independently on transient failures.
        5. Invoke *on_progress* after every resolved batch.
        6. Collate results and return the aggregated report.

        Parameters
        ----------
        document_id :
            Parent document UUID — stored in the result for traceability.
        chunks :
            List of :class:`DocumentChunk` objects to embed.
        on_progress :
            Optional async (or sync) callable receiving an
            :class:`EmbeddingProgress` after every batch.

        Returns
        -------
        EmbeddingBatchResult
        """
        if not chunks:
            logger.warning(f"embed_chunks called with empty list | doc={document_id}")
            return EmbeddingBatchResult(
                document_id=document_id,
                total=0,
                succeeded=0,
                failed=0,
                cache_hits=0,
                embeddings=[],
            )

        total = len(chunks)
        logger.info(f"Embedding started | doc={document_id} | chunks={total}")

        # ── Step 1: cache resolution ───────────────────────────────────────────
        cached_records: list[EmbeddingRecord] = []
        uncached_chunks: list[DocumentChunk] = []

        for chunk in chunks:
            hit = await self._cache.get(chunk.text)
            if hit is not None:
                cached_records.append(
                    EmbeddingRecord(
                        chunk_id=chunk.chunk_id,
                        vector=hit.vector,
                        model=hit.model,
                        cached=True,
                        created_at=hit.created_at,
                    )
                )
            else:
                uncached_chunks.append(chunk)

        cache_hits = len(cached_records)
        if cache_hits:
            logger.info(f"Cache hits | doc={document_id} | hits={cache_hits}/{total}")

        # ── Step 2: batch partitioning ─────────────────────────────────────────
        batches = _partition(uncached_chunks, self._batch_size)

        # Shared mutable accumulators (all writes happen in the gather tasks).
        api_records: list[EmbeddingRecord] = []
        failed_chunk_ids: list[str] = []

        processed_so_far = cache_hits

        # ── Step 3 & 4: concurrent batched API calls ───────────────────────────
        async def _process_batch(batch: list[DocumentChunk]) -> None:
            nonlocal processed_so_far
            records, failed = await self._embed_batch_with_retry(batch)
            api_records.extend(records)
            failed_chunk_ids.extend(failed)
            processed_so_far += len(batch)

            # ── Step 5: progress callback ──────────────────────────────────────
            if on_progress is not None:
                progress = EmbeddingProgress(
                    document_id=document_id,
                    processed=processed_so_far,
                    total=total,
                    cache_hits=cache_hits,
                    failed=len(failed_chunk_ids),
                )
                result = on_progress(progress)
                if asyncio.iscoroutine(result):
                    await result

        await asyncio.gather(*(_process_batch(b) for b in batches))

        # ── Step 6: aggregate ──────────────────────────────────────────────────
        all_records = cached_records + api_records
        succeeded = len(all_records)
        failed_count = len(failed_chunk_ids)

        logger.info(
            f"Embedding complete | doc={document_id} | "
            f"succeeded={succeeded} | failed={failed_count} | "
            f"cache_hits={cache_hits}"
        )

        if failed_count:
            logger.warning(
                f"Failed chunk IDs | doc={document_id} | ids={failed_chunk_ids}"
            )

        return EmbeddingBatchResult(
            document_id=document_id,
            total=total,
            succeeded=succeeded,
            failed=failed_count,
            cache_hits=cache_hits,
            embeddings=all_records,
        )

    async def embed_text(self, text: str) -> EmbeddingVector:
        """
        Embed a single arbitrary string and return its vector.

        Uses the cache transparently; intended for query-time embedding
        once retrieval is implemented.
        """
        hit = await self._cache.get(text)
        if hit is not None:
            logger.debug("Single embed cache hit")
            return hit.vector

        client = self._get_client()
        vector = await self._call_api_single(client, text)
        await self._cache.put(text, "_query_", vector, self._model)
        return vector

    # ── Private: API client ────────────────────────────────────────────────────

    def _get_client(self) -> genai.Client:
        """Return the lazily-initialised Gemini client (one per service instance)."""
        if self._client is None:
            if not self._api_key:
                raise ServiceError(
                    "GEMINI_API_KEY is not configured. "
                    "Set it in your .env file or environment."
                )
            self._client = genai.Client(api_key=self._api_key)
            logger.debug("Gemini client initialised")
        return self._client

    # ── Private: retry logic ───────────────────────────────────────────────────

    async def _embed_batch_with_retry(
        self, batch: list[DocumentChunk]
    ) -> tuple[list[EmbeddingRecord], list[str]]:
        """
        Attempt to embed *batch* up to ``max_retries`` times.

        On success returns ``(records, [])``.
        On exhausted retries returns ``([], failed_chunk_ids)``.
        Partial failures within one batch are not possible because the Gemini
        API either succeeds for all items or raises an exception — so the
        whole batch is retried together.
        """
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                async with self._semaphore:
                    records = await self._call_api_batch(batch)
                return records, []
            except Exception as exc:
                last_exc = exc
                if not _is_retryable(exc):
                    logger.error(
                        f"Non-retryable embedding error | "
                        f"chunks={[c.chunk_id for c in batch]} | {exc!r}"
                    )
                    break

                delay = _jittered_backoff(attempt, self._retry_base)
                logger.warning(
                    f"Embedding retry {attempt + 1}/{self._max_retries} | "
                    f"delay={delay:.2f}s | error={exc!r}"
                )
                await asyncio.sleep(delay)

        logger.error(
            f"Batch embedding failed after retries | "
            f"chunks={[c.chunk_id for c in batch]} | last_error={last_exc!r}"
        )
        return [], [c.chunk_id for c in batch]

    # ── Private: Gemini API calls ──────────────────────────────────────────────

    async def _call_api_batch(self, batch: list[DocumentChunk]) -> list[EmbeddingRecord]:
        """
        Call the Gemini embedding API for an entire batch and write results
        to the cache.

        Uses ``client.aio.models.embed_content`` with each text wrapped in a
        ``types.Content`` object to guarantee per-item treatment (required for
        gemini-embedding-2* models).
        """
        client = self._get_client()
        texts = [c.text for c in batch]

        contents = [
            genai_types.Content(parts=[genai_types.Part(text=t)]) for t in texts
        ]

        response = await client.aio.models.embed_content(
            model=self._model,
            contents=contents,
        )

        # ``response.embeddings`` is a list of ``ContentEmbedding`` objects.
        embeddings_out = response.embeddings  # type: ignore[union-attr]

        if len(embeddings_out) != len(batch):
            raise ServiceError(
                f"API returned {len(embeddings_out)} embeddings for "
                f"{len(batch)} chunks — length mismatch."
            )

        records: list[EmbeddingRecord] = []
        now = datetime.now(timezone.utc)

        for chunk, embedding_obj in zip(batch, embeddings_out, strict=True):
            vector: EmbeddingVector = list(embedding_obj.values)  # type: ignore[arg-type]
            record = EmbeddingRecord(
                chunk_id=chunk.chunk_id,
                vector=vector,
                model=self._model,
                cached=False,
                created_at=now,
            )
            records.append(record)
            # Populate cache in the background (fire-and-forget).
            asyncio.ensure_future(
                self._cache.put(chunk.text, chunk.chunk_id, vector, self._model)
            )

        return records

    async def _call_api_single(self, client: genai.Client, text: str) -> EmbeddingVector:
        """Embed a single text string — used by :meth:`embed_text`."""
        content = genai_types.Content(parts=[genai_types.Part(text=text)])
        response = await client.aio.models.embed_content(
            model=self._model,
            contents=[content],
        )
        embeddings_out = response.embeddings  # type: ignore[union-attr]
        if not embeddings_out:
            raise ServiceError("Gemini returned an empty embedding list for single text.")
        return list(embeddings_out[0].values)  # type: ignore[arg-type]


# ── Module-level helpers ───────────────────────────────────────────────────────


def _partition(items: list[DocumentChunk], size: int) -> list[list[DocumentChunk]]:
    """Split *items* into consecutive chunks of at most *size* length."""
    if size <= 0:
        raise ValueError(f"batch_size must be positive, got {size}")
    return [items[i : i + size] for i in range(0, len(items), size)]


def _is_retryable(exc: Exception) -> bool:
    """
    Return ``True`` if *exc* is a transient error worth retrying.

    Inspects common google-genai / httpx exception attributes.
    """
    msg = str(exc).lower()
    # Rate-limit or server errors mentioned in the message.
    for keyword in ("429", "quota", "rate", "500", "502", "503", "504", "unavailable"):
        if keyword in msg:
            return True
    # google.api_core / google.genai expose a ``status_code`` or ``code`` attr.
    for attr in ("status_code", "code"):
        code = getattr(exc, attr, None)
        if isinstance(code, int) and code in _RETRYABLE_STATUS_CODES:
            return True
    return False


def _jittered_backoff(attempt: int, base: float) -> float:
    """
    Full-jitter exponential back-off.

    ``delay = random(0, base * 2 ** attempt)`` — prevents thundering herd on
    retries from multiple concurrent tasks.
    """
    cap = base * math.pow(2, attempt)
    return random.uniform(0, cap)  # noqa: S311
