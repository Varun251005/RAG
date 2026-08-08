"""
Documents API Router — handling PDF uploads, metadata listing, single document retrieval, and vector deletion.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from loguru import logger

from app.api.deps import get_ingestion_service, get_vector_store_service
from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.chat_api import (
    DocumentInfoResponse,
    DocumentListApiResponse,
    DocumentUploadIngestResponse,
)
from app.services.ingestion_service import DocumentIngestionService
from app.services.vector_store_service import VectorStoreService

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentUploadIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a PDF document",
    description=(
        "Accepts a PDF file, validates format, extracts text page-by-page, "
        "chunks text, generates 384-dim CPU embeddings, and stores vectors in ChromaDB."
    ),
)
async def upload_pdf_document(
    file: UploadFile = File(..., description="PDF document file"),
    ingestion_service: DocumentIngestionService = Depends(get_ingestion_service),
) -> DocumentUploadIngestResponse:
    filename = file.filename or "uploaded.pdf"

    # Validate PDF content type / extension
    if not filename.lower().endswith(".pdf"):
        raise UnprocessableError(f"File '{filename}' is not a valid PDF file.")

    content = await file.read()
    if not content:
        raise UnprocessableError("Uploaded file content is empty.")

    # Validate magic header signature (%PDF-)
    if not content.startswith(b"%PDF-"):
        raise UnprocessableError(f"File '{filename}' is not a valid PDF document (invalid magic header).")

    logger.info(f"Uploading & ingesting PDF | filename={filename} | size_bytes={len(content)}")

    res = await ingestion_service.ingest_pdf_bytes(
        pdf_bytes=content,
        filename=filename,
    )

    return DocumentUploadIngestResponse(
        document_id=res["document_id"],
        filename=res["filename"],
        total_pages=res["total_pages"],
        total_chunks=res["total_chunks"],
        status=res["status"],
    )


@router.get(
    "",
    response_model=DocumentListApiResponse,
    summary="List all indexed documents",
)
async def list_indexed_documents(
    vector_store: VectorStoreService = Depends(get_vector_store_service),
) -> DocumentListApiResponse:
    """Return all distinct indexed documents in ChromaDB."""
    try:
        col = await vector_store.get_or_create_collection()
        raw = col.get(include=["metadatas"])
        metadatas = raw.get("metadatas") or []

        doc_summary: dict[str, dict[str, Any]] = {}
        for meta in metadatas:
            if not meta:
                continue
            doc_id = str(meta.get("document_id", ""))
            fname = str(meta.get("source_filename", "unknown.pdf"))
            if doc_id:
                if doc_id not in doc_summary:
                    doc_summary[doc_id] = {"document_id": doc_id, "filename": fname, "total_chunks": 0}
                doc_summary[doc_id]["total_chunks"] += 1

        docs = [DocumentInfoResponse(**info) for info in doc_summary.values()]
        return DocumentListApiResponse(documents=docs, total=len(docs))
    except Exception as exc:
        logger.error(f"Failed to list documents: {exc}")
        return DocumentListApiResponse(documents=[], total=0)


@router.get(
    "/{doc_id}",
    response_model=DocumentInfoResponse,
    summary="Get document details by ID",
)
async def get_document_details(
    doc_id: str,
    vector_store: VectorStoreService = Depends(get_vector_store_service),
) -> DocumentInfoResponse:
    """Retrieve indexed document information by document_id."""
    col = await vector_store.get_or_create_collection()
    raw = col.get(where={"document_id": doc_id}, include=["metadatas"])
    metadatas = raw.get("metadatas") or []

    if not metadatas:
        raise NotFoundError("Document", doc_id)

    filename = str(metadatas[0].get("source_filename", "unknown.pdf"))
    return DocumentInfoResponse(
        document_id=doc_id,
        filename=filename,
        total_chunks=len(metadatas),
    )


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete an indexed document by ID",
)
async def delete_indexed_document(
    doc_id: str,
    vector_store: VectorStoreService = Depends(get_vector_store_service),
) -> dict[str, str]:
    """Delete all vector chunks associated with document_id from ChromaDB."""
    col = await vector_store.get_or_create_collection()
    raw = col.get(where={"document_id": doc_id}, include=["metadatas"])
    metadatas = raw.get("metadatas") or []

    if not metadatas:
        raise NotFoundError("Document", doc_id)

    await vector_store.delete_document(document_id=doc_id)
    from app.api.deps import get_bm25_service
    get_bm25_service().delete_document(document_id=doc_id)
    return {"message": f"Document '{doc_id}' deleted successfully.", "document_id": doc_id}
