import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.exceptions import ConflictError, NotFoundError, ServiceError, UnprocessableError
from app.models.document import (
    DocumentListResponse,
    DocumentRecord,
    DocumentResponse,
    DocumentStatus,
)
from app.utils.file_utils import (
    FileValidationError,
    compute_sha256,
    sanitize_filename,
    validate_pdf,
)


class DocumentService:
    """
    Manages PDF document storage and retrieval.

    Storage layout on disk:
        {upload_dir}/
            {doc_id}/
                {sanitized_name}.pdf
                meta.json          ← DocumentRecord serialised as JSON
    """

    def __init__(self, upload_dir: Path, max_upload_bytes: int) -> None:
        self._root = upload_dir
        self._max_bytes = max_upload_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    # ── Public interface ───────────────────────────────────────────────────────

    async def upload(
        self, filename: str, content: bytes, content_type: str
    ) -> DocumentResponse:
        """Validate, deduplicate, persist, and return metadata for one PDF."""
        self._validate(filename, content, content_type)

        file_hash = compute_sha256(content)
        self._reject_if_duplicate(file_hash)

        record = self._persist(filename, content, content_type, file_hash)

        logger.info(
            f"Document stored | id={record.id} | "
            f"filename={record.filename} | bytes={record.size_bytes}"
        )
        return _to_response(record)

    async def list_documents(self) -> DocumentListResponse:
        """Return all documents ordered newest-first."""
        records = self._load_all_records()
        records.sort(key=lambda r: r.created_at, reverse=True)
        return DocumentListResponse(
            documents=[_to_response(r) for r in records],
            total=len(records),
        )

    async def delete(self, doc_id: str) -> None:
        """Remove a document directory and all its contents + Chroma vector embeddings."""
        doc_dir = self._root / doc_id
        if not doc_dir.is_dir():
            raise NotFoundError("Document", doc_id)

        # 1. Clean up ChromaDB embeddings if present
        try:
            from app.api.deps import get_vector_store_service
            vec_svc = get_vector_store_service()
            await vec_svc.delete_document(doc_id)
            logger.info(f"Purged vector store chunks for document | id={doc_id}")
        except Exception as exc:
            logger.warning(f"Vector store deletion skipped/failed | id={doc_id} | error={exc}")

        # 2. Delete file system directory
        try:
            shutil.rmtree(doc_dir)
            logger.info(f"Document file deleted | id={doc_id}")
        except OSError as exc:
            logger.error(f"Delete failed | id={doc_id} | error={exc}")
            raise ServiceError("Could not delete the document.") from exc


    async def get_file_path(self, doc_id: str) -> Path:
        """Return absolute path to stored PDF file for a document ID."""
        records = self._load_all_records()
        for r in records:
            if r.id == doc_id:
                p = Path(r.upload_path)
                if p.exists():
                    return p
                break
        raise NotFoundError("Document file", doc_id)


    # ── Private helpers ────────────────────────────────────────────────────────

    def _validate(self, filename: str, content: bytes, content_type: str) -> None:
        try:
            validate_pdf(filename, content, content_type, self._max_bytes)
        except FileValidationError as exc:
            raise UnprocessableError(str(exc)) from exc

    def _reject_if_duplicate(self, file_hash: str) -> None:
        existing = self._find_by_hash(file_hash)
        if existing:
            raise ConflictError(
                f"Identical content already uploaded as "
                f"'{existing.original_filename}' (id={existing.id})."
            )

    def _persist(
        self, filename: str, content: bytes, content_type: str, file_hash: str
    ) -> DocumentRecord:
        doc_id = str(uuid.uuid4())
        safe_stem = sanitize_filename(filename)
        stored_name = f"{safe_stem}.pdf"

        doc_dir = self._root / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        try:
            (doc_dir / stored_name).write_bytes(content)
        except OSError as exc:
            logger.error(f"Write failed | id={doc_id} | error={exc}")
            raise ServiceError("Could not write the uploaded file.") from exc

        record = DocumentRecord(
            id=doc_id,
            filename=stored_name,
            original_filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            file_hash=file_hash,
            status=DocumentStatus.READY,
            upload_path=str(doc_dir / stored_name),
            created_at=datetime.now(timezone.utc),
        )
        self._write_meta(doc_dir, record)
        return record

    def _write_meta(self, doc_dir: Path, record: DocumentRecord) -> None:
        (doc_dir / "meta.json").write_text(record.model_dump_json(indent=2))

    def _load_all_records(self) -> list[DocumentRecord]:
        records: list[DocumentRecord] = []
        for doc_dir in self._root.iterdir():
            meta = doc_dir / "meta.json"
            if not doc_dir.is_dir() or not meta.exists():
                continue
            try:
                records.append(DocumentRecord.model_validate_json(meta.read_text()))
            except Exception as exc:
                logger.warning(f"Skipping corrupt metadata | dir={doc_dir} | {exc}")
        return records

    def _find_by_hash(self, file_hash: str) -> DocumentRecord | None:
        for record in self._load_all_records():
            if record.file_hash == file_hash:
                return record
        return None


def _to_response(record: DocumentRecord) -> DocumentResponse:
    """Convert internal record to the public API shape."""
    return DocumentResponse(
        id=record.id,
        filename=record.filename,
        original_filename=record.original_filename,
        size_bytes=record.size_bytes,
        status=record.status,
        created_at=record.created_at,
    )
