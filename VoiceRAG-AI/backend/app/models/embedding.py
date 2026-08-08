"""Pydantic models for the embedding pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# A single embedding vector (list of floats from the Gemini API).
EmbeddingVector = list[float]


class EmbeddingRecord(BaseModel):
    """
    A fully resolved embedding for one document chunk.

    ``chunk_id``  — matches ``DocumentChunk.chunk_id`` for easy join.
    ``vector``    — the raw float vector from Gemini.
    ``model``     — the embedding model used (e.g. ``text-embedding-004``).
    ``cached``    — ``True`` if this result was served from cache.
    ``created_at``— UTC timestamp of when the embedding was computed/loaded.
    """

    chunk_id: str
    vector: Annotated[EmbeddingVector, Field(min_length=1)]
    model: str
    cached: bool = False
    created_at: datetime

    model_config = ConfigDict(frozen=True)


class EmbeddingBatchResult(BaseModel):
    """
    Output of a single :class:`EmbeddingService.embed_chunks` call.

    ``document_id``   — UUID of the parent document.
    ``total``         — total chunks submitted.
    ``succeeded``     — chunks that received a valid embedding.
    ``failed``        — chunk IDs that could not be embedded after retries.
    ``cache_hits``    — how many were served from cache without an API call.
    ``embeddings``    — list of :class:`EmbeddingRecord`, one per succeeded chunk.
    """

    document_id: str
    total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    embeddings: list[EmbeddingRecord]

    model_config = ConfigDict(frozen=True)


class EmbeddingProgress(BaseModel):
    """
    Snapshot emitted by the progress callback during a batch embedding run.

    Consumers can use this to drive a progress bar or structured log line.
    """

    document_id: str
    processed: int = Field(ge=0)
    total: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    failed: int = Field(ge=0)

    @property
    def percent(self) -> float:
        """Completion percentage (0–100)."""
        return (self.processed / self.total * 100) if self.total else 0.0

    model_config = ConfigDict(frozen=True)


# ── Cache entry (persisted to disk as JSON) ────────────────────────────────────


class CachedEmbedding(BaseModel):
    """Schema for a cache entry written to / read from the disk cache."""

    chunk_id: str
    text_hash: str  # SHA-256 of the chunk text — key for cache lookup
    vector: EmbeddingVector
    model: str
    created_at: datetime

    model_config = ConfigDict(frozen=True)
