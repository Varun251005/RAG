from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class DocumentStatus(str, Enum):
    READY = "ready"
    FAILED = "failed"


class DocumentRecord(BaseModel):
    """Internal record persisted alongside each uploaded file."""

    id: str
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    file_hash: str
    status: DocumentStatus
    upload_path: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """Public API representation of an uploaded document."""

    id: str
    filename: str
    original_filename: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime


class UploadError(BaseModel):
    """Describes a single failed upload within a bulk request."""

    original_filename: str
    reason: str


class BulkUploadResponse(BaseModel):
    """Returned by the bulk upload endpoint — partial success is possible."""

    uploaded: list[DocumentResponse]
    failed: list[UploadError]


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
