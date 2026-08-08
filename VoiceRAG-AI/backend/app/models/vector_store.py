"""Pydantic models for ChromaDB operations — store, search, and management."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Storage input
# ---------------------------------------------------------------------------


class VectorDocument(BaseModel):
    """
    A single item ready to be upserted into a ChromaDB collection.

    Built from a ``DocumentChunk`` + ``EmbeddingRecord`` pair by the caller.

    Fields
    ------
    id :
        Unique identifier — must match ``DocumentChunk.chunk_id`` so rows
        are idempotently upsertable.
    embedding :
        Float vector from the embedding pipeline.
    text :
        Raw chunk text stored as the Chroma ``document`` field.
    metadata :
        Flat key/value dict written to Chroma's metadata store.
        Only ``str | int | float | bool`` values are supported by Chroma;
        complex types (lists, dicts) must be serialised to strings before
        passing here.
    """

    id: str
    embedding: list[float] = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Storage output
# ---------------------------------------------------------------------------


class UpsertResult(BaseModel):
    """Returned after a batch upsert into ChromaDB."""

    collection: str
    upserted: int = Field(ge=0)
    document_id: str  # parent document UUID for traceability

    model_config = ConfigDict(frozen=True)


class DeleteResult(BaseModel):
    """Returned after deleting all chunks for a document."""

    collection: str
    document_id: str
    deleted: int = Field(ge=0)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    """
    A single document returned from a similarity search.

    ``id``        — chunk ID.
    ``text``      — raw chunk text.
    ``metadata``  — associated metadata dict.
    ``distance``  — L2 / cosine distance from the query vector (lower = closer).
    ``score``     — 1 − distance, for intuitive "higher = more relevant" ordering.
    """

    id: str
    text: str
    metadata: dict[str, Any]
    distance: float
    score: float

    model_config = ConfigDict(frozen=True)


class SearchResponse(BaseModel):
    """Container for a similarity search response."""

    query: str
    collection: str
    results: list[SearchResult]
    total_returned: int = Field(ge=0)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Collection info
# ---------------------------------------------------------------------------


class CollectionInfo(BaseModel):
    """Metadata about a ChromaDB collection."""

    name: str
    count: int = Field(ge=0)  # total documents (chunks) in the collection

    model_config = ConfigDict(frozen=True)
