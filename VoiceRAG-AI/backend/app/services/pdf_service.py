"""
PDF Processing Service for VoiceRAG AI.

Uses PyMuPDF (pymupdf) for page-by-page text extraction and metadata extraction.
Validates PDF headers, handles empty pages gracefully, detects unprocessable / image-only
PDFs with no extractable text, and saves files in configurable upload storage directories.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

import pymupdf
from loguru import logger

from app.core.exceptions import UnprocessableError



class PDFValidationError(UnprocessableError):
    """Raised when PDF file header or structure is invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.message = detail

    def __str__(self) -> str:
        return self.detail


class PDFProcessingError(UnprocessableError):
    """Raised when PDF content cannot be extracted or processed."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.message = detail

    def __str__(self) -> str:
        return self.detail




class PDFProcessingService:
    """
    Service responsible for PDF validation, local file persistence,
    and page-by-page text extraction.
    """

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else Path("uploads")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def validate_pdf_bytes(self, content: bytes, filename: str = "document.pdf") -> None:
        """
        Validate that the provided bytes represent a valid non-empty PDF document.
        """
        if not content:
            raise PDFValidationError("PDF file content is empty.")

        # Header signature validation (%PDF-)
        if not content.startswith(b"%PDF-"):
            raise PDFValidationError(f"File '{filename}' is not a valid PDF document (invalid magic header).")

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            if doc.page_count < 1:
                doc.close()
                raise PDFValidationError(f"PDF '{filename}' contains 0 pages.")
            doc.close()
        except Exception as exc:
            if isinstance(exc, PDFValidationError):
                raise
            raise PDFValidationError(f"Failed to parse PDF document '{filename}': {exc}") from exc


    def extract_text_from_bytes(
        self,
        content: bytes,
        filename: str = "document.pdf",
        doc_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Extract page-by-page text and metadata from PDF bytes.

        Returns:
            dict with structure:
            {
                "document_id": "...",
                "filename": "...",
                "total_pages": int,
                "pages": [
                    {"page_number": 1, "text": "..."},
                    ...
                ]
            }
        """
        self.validate_pdf_bytes(content, filename)

        document_id = doc_id or f"doc_{uuid.uuid4().hex[:12]}"
        pages: list[dict[str, Any]] = []
        total_text_length = 0

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            total_pages = doc.page_count

            for page_idx in range(total_pages):
                page = doc.load_page(page_idx)
                page_number = page_idx + 1
                extracted = page.get_text("text") or ""
                clean_text = extracted.strip()

                pages.append({
                    "page_number": page_number,
                    "text": clean_text,
                })
                total_text_length += len(clean_text)

            doc.close()
        except Exception as exc:
            raise PDFProcessingError(f"Error extracting text from PDF '{filename}': {exc}") from exc

        # Detect PDFs with no usable text (scanned / image-only / empty)
        if total_text_length == 0:
            raise PDFProcessingError(
                f"PDF '{filename}' contains no usable text. It may be a scanned image or empty PDF."
            )

        logger.info(
            f"Extracted PDF text | doc_id={document_id} | filename={filename} | "
            f"pages={len(pages)} | total_chars={total_text_length}"
        )

        return {
            "document_id": document_id,
            "filename": filename,
            "total_pages": len(pages),
            "pages": pages,
        }

    def save_pdf(self, content: bytes, filename: str, doc_id: str | None = None) -> Path:
        """
        Save PDF bytes to the local storage directory under a unique document folder.
        """
        self.validate_pdf_bytes(content, filename)

        document_id = doc_id or f"doc_{uuid.uuid4().hex[:12]}"
        target_dir = self.storage_dir / document_id
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / filename
        target_file.write_bytes(content)
        return target_file
