"""Pydantic models for the RAG query pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class RAGQuery(BaseModel):
    """
    Incoming RAG query from the client.

    Fields
    ------
    question :
        The natural-language question to answer.
    collection :
        ChromaDB collection to search.  Defaults to ``Settings.chroma_collection``.
    top_k :
        Number of document chunks to retrieve (1–20).
    document_id :
        Optional UUID — restricts search to chunks from a single document.
    """

    question: str = Field(min_length=1, max_length=2000, description="The question to answer.")
    collection: str | None = Field(default=None, description="ChromaDB collection name.")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve.")
    document_id: str | None = Field(
        default=None,
        description="Restrict search to a single document (optional).",
    )

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Source citation
# ---------------------------------------------------------------------------


class RAGSource(BaseModel):
    """
    A single source chunk cited in a RAG answer.

    Returned alongside the answer so clients can render citations,
    highlight pages, and link back to the original document.
    """

    chunk_id: str = Field(description="Unique chunk identifier.")
    snippet: str = Field(description="First 250 characters of the chunk text.")
    page_number: int = Field(ge=1, description="1-indexed source page.")
    original_filename: str = Field(description="Human-readable source filename.")
    score: float = Field(description="Cosine similarity score (0–1, higher = more relevant).")
    document_id: str = Field(description="UUID of the parent document.")

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Batch response
# ---------------------------------------------------------------------------


class RAGResponse(BaseModel):
    """Full (non-streaming) RAG response returned by POST /rag/query."""

    question: str
    answer: str
    sources: list[RAGSource]
    total_chunks_used: int = Field(ge=0)
    model: str = Field(description="LLM model name used for generation.")

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------


class RAGStreamToken(BaseModel):
    """Payload carried by an SSE ``token`` event."""

    text: str

    model_config = ConfigDict(frozen=True)


class RAGStreamSources(BaseModel):
    """Payload carried by the terminal SSE ``sources`` event."""

    sources: list[RAGSource]
    total_chunks_used: int = Field(ge=0)

    model_config = ConfigDict(frozen=True)


class RAGStreamError(BaseModel):
    """Payload carried by an SSE ``error`` event."""

    detail: str

    model_config = ConfigDict(frozen=True)
