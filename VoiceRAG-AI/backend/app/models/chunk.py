"""Pydantic models for document chunks produced by the chunking pipeline."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkMetadata(BaseModel):
    """
    Metadata propagated from the source document into every chunk.

    Fields are intentionally broad so they can carry page-level information
    from any PDF parser (e.g. pypdf, pdfplumber) without schema changes.
    """

    document_id: str = Field(description="UUID of the parent DocumentRecord.")
    original_filename: str = Field(description="Human-readable source filename.")
    page_number: int = Field(ge=1, description="1-indexed page the chunk originates from.")
    total_pages: int = Field(ge=1, description="Total pages in the source document.")

    # Arbitrary key/value pairs from the PDF reader (title, author, etc.).
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional PDF metadata (title, author, subject…).",
    )

    model_config = ConfigDict(frozen=True)


class DocumentChunk(BaseModel):
    """
    A single text chunk ready for embedding / storage.

    Design decisions
    ----------------
    * ``chunk_id``      — deterministic ``<doc_id>_p<page>_c<seq>`` so the
                          vector store can upsert idempotently.
    * ``chunk_index``   — 0-based position across *all* chunks for a document.
    * ``metadata``      — rich provenance; page number is always preserved.
    * ``text``          — raw chunk content; never empty.
    """

    chunk_id: str = Field(description="Unique identifier for this chunk.")
    chunk_index: int = Field(ge=0, description="0-based sequential position in the document.")
    text: str = Field(min_length=1, description="Chunk text content.")
    metadata: ChunkMetadata

    model_config = ConfigDict(frozen=True)


class ChunkingResult(BaseModel):
    """Aggregated output returned by the chunking service for one document."""

    document_id: str
    total_chunks: int = Field(ge=0)
    chunks: list[DocumentChunk]

    model_config = ConfigDict(frozen=True)
