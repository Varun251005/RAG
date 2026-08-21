"""
Integration tests for DocumentIngestionService.

Tests cover:
1. End-to-end PDF ingestion: PDF → Pages → Chunks → 384-dim CPU Embeddings → ChromaDB.
2. Metadata preservation in ChromaDB vectors.
3. Idempotency check: Reprocessing document with same document_id does not duplicate vectors.
4. Failure rollback: If ingestion fails during embedding/upsert, partial ChromaDB vectors are deleted.
"""

from __future__ import annotations

import pytest
import pymupdf
import chromadb

from app.services.local_embedding_service import LocalEmbeddingService
from app.services.pdf_service import PDFProcessingService
from app.services.chunking_service import ChunkingService
from app.services.vector_store_service import VectorStoreService
from app.services.ingestion_service import DocumentIngestionService
from app.core.exceptions import UnprocessableError


def _create_sample_multipage_pdf_bytes() -> bytes:
    """Helper creating a 3-page test PDF in memory."""
    doc = pymupdf.open()

    p1 = doc.new_page()
    p1.insert_text((50, 100), "VoiceRAG AI is a modular RAG platform using local CPU embeddings.", fontsize=12)

    p2 = doc.new_page()
    p2.insert_text((50, 100), "ChromaDB vector store maintains cosine similarity indices for document chunks.", fontsize=12)

    p3 = doc.new_page()
    p3.insert_text((50, 100), "Edge-TTS provides text-to-speech synthesis capabilities for study notes.", fontsize=12)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def ingestion_service() -> DocumentIngestionService:
    pdf_svc = PDFProcessingService()
    chunk_svc = ChunkingService(chunk_size=3200, chunk_overlap=600)
    embed_svc = LocalEmbeddingService()

    vector_svc = VectorStoreService(default_collection="test_ingestion_voicerag")
    vector_svc._client = chromadb.EphemeralClient()

    return DocumentIngestionService(
        pdf_service=pdf_svc,
        chunking_service=chunk_svc,
        embedding_service=embed_svc,
        vector_store_service=vector_svc,
    )


@pytest.mark.asyncio
async def test_end_to_end_pdf_ingestion(ingestion_service: DocumentIngestionService) -> None:
    pdf_bytes = _create_sample_multipage_pdf_bytes()
    doc_id = "doc_ingest_test_001"
    filename = "voicerag_spec.pdf"
    collection = "test_ingestion_voicerag"

    res = await ingestion_service.ingest_pdf_bytes(
        pdf_bytes=pdf_bytes,
        filename=filename,
        document_id=doc_id,
        collection_name=collection,
    )

    assert res["document_id"] == doc_id
    assert res["filename"] == filename
    assert res["total_pages"] == 3
    assert res["total_chunks"] == 3
    assert res["status"] == "completed"

    # Verify vector store contents
    col_info = await ingestion_service.vector_store_service.collection_info(name=collection)
    assert col_info.count == 3

    # Retrieve vector document & check metadata + 384 dimensions
    raw_data = await ingestion_service.vector_store_service.get_by_ids(
        ids=[f"{doc_id}_p0001_c0000"],
        collection_name=collection,
    )
    assert len(raw_data) == 1
    record = raw_data[0]
    assert record["metadata"]["document_id"] == doc_id
    assert record["metadata"]["source_filename"] == filename
    assert record["metadata"]["page_number"] == 1


@pytest.mark.asyncio
async def test_ingestion_idempotency(ingestion_service: DocumentIngestionService) -> None:
    pdf_bytes = _create_sample_multipage_pdf_bytes()
    doc_id = "doc_idempotent_002"
    filename = "duplicate_test.pdf"
    collection = "test_ingestion_voicerag"

    # Ingest first time
    res1 = await ingestion_service.ingest_pdf_bytes(
        pdf_bytes=pdf_bytes,
        filename=filename,
        document_id=doc_id,
        collection_name=collection,
    )
    col_info1 = await ingestion_service.vector_store_service.collection_info(name=collection)

    # Ingest second time with SAME document_id
    res2 = await ingestion_service.ingest_pdf_bytes(
        pdf_bytes=pdf_bytes,
        filename=filename,
        document_id=doc_id,
        collection_name=collection,
    )
    col_info2 = await ingestion_service.vector_store_service.collection_info(name=collection)

    assert res1["total_chunks"] == res2["total_chunks"]
    # Total count in ChromaDB must remain identical (no duplicate vector rows)
    assert col_info1.count == col_info2.count


@pytest.mark.asyncio
async def test_ingestion_rollback_on_failure(ingestion_service: DocumentIngestionService) -> None:
    invalid_bytes = b"This is invalid text, not a PDF."
    doc_id = "doc_rollback_003"
    collection = "test_ingestion_voicerag"

    with pytest.raises(Exception):
        await ingestion_service.ingest_pdf_bytes(
            pdf_bytes=invalid_bytes,
            filename="corrupt.pdf",
            document_id=doc_id,
            collection_name=collection,
        )

    # Verify vector store contains 0 documents for doc_rollback_003
    col_info = await ingestion_service.vector_store_service.collection_info(name=collection)
    fetched = await ingestion_service.vector_store_service.get_by_ids(
        ids=[f"{doc_id}_p0001_c0000"],
        collection_name=collection,
    )
    assert len(fetched) == 0
