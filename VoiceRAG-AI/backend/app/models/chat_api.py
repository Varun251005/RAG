"""
Pydantic Request and Response schemas for RAG HTTP API endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentUploadIngestResponse(BaseModel):
    """Returned upon successful PDF upload and vector ingestion."""

    document_id: str
    filename: str
    total_pages: int
    total_chunks: int
    status: str = "completed"


class ChatRequest(BaseModel):
    """Request payload for RAG chat endpoint."""

    question: str = Field(..., description="User question text to query documents.")
    document_id: str | None = Field(default=None, description="Optional target document ID to filter query.")


class ChatSourceCitation(BaseModel):
    """Source reference citation for RAG answer."""

    document_id: str
    filename: str
    page_number: int
    chunk_id: str


class ChatResponse(BaseModel):
    """Response returned by the RAG chat endpoint."""

    answer: str
    sources: list[ChatSourceCitation]


class DocumentInfoResponse(BaseModel):
    """Summary representation of an indexed document in the vector store."""

    document_id: str
    filename: str
    total_chunks: int


class DocumentListApiResponse(BaseModel):
    """List of all indexed documents in the vector store."""

    documents: list[DocumentInfoResponse]
    total: int
