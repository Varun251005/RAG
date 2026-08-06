from fastapi import APIRouter, Depends, File, UploadFile, status
from loguru import logger

from app.api.deps import get_document_service
from app.models.document import (
    BulkUploadResponse,
    DocumentListResponse,
    DocumentResponse,
    UploadError,
)
from app.core.exceptions import AppException
from app.services.document_service import DocumentService

router = APIRouter()


@router.post(
    "",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Upload one or more PDF documents",
    description=(
        "Accepts multiple PDF files in a single request. "
        "Each file is validated, deduplicated, and stored independently. "
        "Partial success is possible — check `failed` for per-file errors."
    ),
)
async def upload_documents(
    files: list[UploadFile] = File(..., description="One or more PDF files (max 25 MB each)"),
    service: DocumentService = Depends(get_document_service),
) -> BulkUploadResponse:
    logger.info(f"Bulk upload request | count={len(files)}")

    uploaded: list[DocumentResponse] = []
    failed: list[UploadError] = []

    for file in files:
        original_name = file.filename or "unnamed.pdf"
        try:
            content = await file.read()
            result = await service.upload(
                filename=original_name,
                content=content,
                content_type=file.content_type or "application/octet-stream",
            )
            uploaded.append(result)
        except AppException as exc:
            logger.warning(f"Upload rejected | filename={original_name} | {exc.message}")
            failed.append(UploadError(original_filename=original_name, reason=exc.detail))

    return BulkUploadResponse(uploaded=uploaded, failed=failed)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all uploaded documents",
)
async def list_documents(
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    return await service.list_documents()


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document by ID",
)
async def delete_document(
    doc_id: str,
    service: DocumentService = Depends(get_document_service),
) -> None:
    await service.delete(doc_id)
