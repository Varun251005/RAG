"""
Documents API Router — handling PDF uploads, metadata listing, single document retrieval, PDF file streaming, and vector deletion.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from loguru import logger

from app.api.deps import get_ingestion_service, get_vector_store_service
from app.core.config import get_settings
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
            page_num = int(meta.get("page_number", 1))
            if doc_id:
                if doc_id not in doc_summary:
                    doc_summary[doc_id] = {
                        "document_id": doc_id,
                        "filename": fname,
                        "total_chunks": 0,
                        "total_pages": 1,
                    }
                doc_summary[doc_id]["total_chunks"] += 1
                if page_num > doc_summary[doc_id]["total_pages"]:
                    doc_summary[doc_id]["total_pages"] = page_num

        docs = [DocumentInfoResponse(**info) for info in doc_summary.values()]
        return DocumentListApiResponse(documents=docs, total=len(docs))
    except Exception as exc:
        logger.error(f"Failed to list documents: {exc}")
        return DocumentListApiResponse(documents=[], total=0)


@router.head("/{doc_id}/file")
@router.get(
    "/{doc_id}/file",
    response_class=FileResponse,
    summary="Retrieve the original PDF file binary",
    description="Returns the raw PDF file for inline browser viewing or downloading.",
)
async def get_document_file(
    doc_id: str,
    vector_store: VectorStoreService = Depends(get_vector_store_service),
) -> FileResponse:
    """Validate doc_id, locate stored PDF binary, and stream with application/pdf media type."""
    import pymupdf

    # Basic path traversal & security check
    if not doc_id or ".." in doc_id or "/" in doc_id or "\\" in doc_id:
        raise NotFoundError("Document file", doc_id)

    # Sanitize doc_id pattern
    if not re.match(r"^[a-zA-Z0-9_\-]+$", doc_id):
        raise NotFoundError("Document file", doc_id)

    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    target_dir = (upload_root / doc_id).resolve()

    # Ensure target path remains within upload directory
    if not target_dir.is_relative_to(upload_root):
        raise NotFoundError("Document file", doc_id)

    pdf_path: Path | None = None

    if target_dir.is_dir():
        # Look for any .pdf file inside document directory
        pdf_files = list(target_dir.glob("*.pdf"))
        if pdf_files:
            pdf_path = pdf_files[0]
    elif target_dir.is_file() and target_dir.name.lower().endswith(".pdf"):
        pdf_path = target_dir
    else:
        # Check direct upload_root / doc_id + ".pdf"
        alt_path = (upload_root / f"{doc_id}.pdf").resolve()
        if alt_path.is_file() and alt_path.is_relative_to(upload_root):
            pdf_path = alt_path

    # Fallback 1: Query ChromaDB for source_filename and search upload_root
    if not pdf_path or not pdf_path.exists():
        try:
            col = await vector_store.get_or_create_collection()
            raw = col.get(where={"document_id": doc_id}, include=["metadatas"])
            metadatas = raw.get("metadatas") or []
            if metadatas and metadatas[0]:
                source_fn = str(metadatas[0].get("source_filename", ""))
                if source_fn:
                    f1 = (upload_root / source_fn).resolve()
                    if f1.is_file() and f1.is_relative_to(upload_root):
                        pdf_path = f1
                    else:
                        for found in upload_root.glob(f"**/{source_fn}"):
                            if found.is_file() and found.resolve().is_relative_to(upload_root):
                                pdf_path = found.resolve()
                                break
        except Exception as e:
            logger.warning(f"Fallback filename lookup failed for {doc_id}: {e}")

    # Fallback 2: Dynamic PDF reconstruction from ChromaDB text chunks if file missing
    if not pdf_path or not pdf_path.exists():
        try:
            col = await vector_store.get_or_create_collection()
            raw = col.get(where={"document_id": doc_id}, include=["metadatas", "documents"])
            metadatas = raw.get("metadatas") or []
            documents = raw.get("documents") or []
            if metadatas:
                source_fn = str(metadatas[0].get("source_filename", f"{doc_id}.pdf"))
                if not source_fn.lower().endswith(".pdf"):
                    source_fn = f"{source_fn}.pdf"

                pages_dict: dict[int, list[str]] = {}
                for idx, meta in enumerate(metadatas):
                    if not meta:
                        continue
                    p_num = int(meta.get("page_number", 1))
                    txt = documents[idx] if idx < len(documents) else ""
                    if p_num not in pages_dict:
                        pages_dict[p_num] = []
                    if txt:
                        pages_dict[p_num].append(txt)

                pdf_doc = pymupdf.open()
                sorted_pages = sorted(pages_dict.keys()) or [1]
                for p_num in sorted_pages:
                    pdf_page = pdf_doc.new_page(width=595, height=842)  # A4 size
                    page_text = f"--- Document: {source_fn} | Page {p_num} ---\n\n" + "\n\n".join(pages_dict.get(p_num, []))
                    rect = pymupdf.Rect(40, 40, 555, 802)
                    pdf_page.insert_textbox(rect, page_text, fontsize=10, fontname="helv")

                out_dir = upload_root / doc_id
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / source_fn
                pdf_doc.save(str(out_file))
                pdf_doc.close()
                pdf_path = out_file
                logger.info(f"Reconstructed PDF for document_id={doc_id} | path={pdf_path}")
        except Exception as e:
            logger.warning(f"PDF reconstruction fallback failed for {doc_id}: {e}")

    if not pdf_path or not pdf_path.exists():
        raise NotFoundError("Document file", doc_id)

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={
            "Content-Disposition": f'inline; filename="{pdf_path.name}"'
        },
    )




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
    total_pages = max(int(m.get("page_number", 1)) for m in metadatas if m)
    return DocumentInfoResponse(
        document_id=doc_id,
        filename=filename,
        total_chunks=len(metadatas),
        total_pages=total_pages,
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
    """Delete all vector chunks associated with document_id from ChromaDB and clean up saved files."""
    col = await vector_store.get_or_create_collection()
    raw = col.get(where={"document_id": doc_id}, include=["metadatas"])
    metadatas = raw.get("metadatas") or []

    if not metadatas:
        raise NotFoundError("Document", doc_id)

    await vector_store.delete_document(document_id=doc_id)
    from app.api.deps import get_bm25_service
    get_bm25_service().delete_document(document_id=doc_id)

    # Delete physical PDF files if stored in uploads directory
    settings = get_settings()
    doc_dir = Path(settings.upload_dir) / doc_id
    if doc_dir.exists():
        if doc_dir.is_dir():
            import shutil
            shutil.rmtree(doc_dir, ignore_errors=True)
        elif doc_dir.is_file():
            doc_dir.unlink(missing_ok=True)

    return {"message": f"Document '{doc_id}' deleted successfully.", "document_id": doc_id}

