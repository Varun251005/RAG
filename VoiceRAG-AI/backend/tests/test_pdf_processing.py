"""
Unit tests for PDFProcessingService.

Tests cover:
- Valid PDF text extraction (single page)
- Multi-page PDF text extraction
- PDF with an empty page
- Invalid non-PDF file handling (validation error)
- PDF with no extractable text (extraction failure error)
"""

from __future__ import annotations

import io
import pytest
import pymupdf

from app.services.pdf_service import (
    PDFProcessingError,
    PDFProcessingService,
    PDFValidationError,
)



def _create_sample_pdf_bytes(pages_text: list[str]) -> bytes:
    """Helper to create an in-memory PDF with specified text per page using PyMuPDF."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            # Insert text at top-left of page
            page.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def pdf_service(tmp_path: pytest.TempPathFactory) -> PDFProcessingService:
    return PDFProcessingService(storage_dir=tmp_path)


def test_extract_valid_single_page_pdf(pdf_service: PDFProcessingService) -> None:
    pdf_bytes = _create_sample_pdf_bytes(["Hello VoiceRAG AI PDF Processing!"])
    res = pdf_service.extract_text_from_bytes(pdf_bytes, filename="sample.pdf")

    assert res["filename"] == "sample.pdf"
    assert res["total_pages"] == 1
    assert len(res["pages"]) == 1
    assert res["pages"][0]["page_number"] == 1
    assert "Hello VoiceRAG AI" in res["pages"][0]["text"]
    assert res["document_id"].startswith("doc_")


def test_extract_multi_page_pdf(pdf_service: PDFProcessingService) -> None:
    pdf_bytes = _create_sample_pdf_bytes([
        "Page One Content - Introduction",
        "Page Two Content - Architecture",
        "Page Three Content - Conclusion",
    ])
    res = pdf_service.extract_text_from_bytes(pdf_bytes, filename="multi.pdf")

    assert res["total_pages"] == 3
    assert len(res["pages"]) == 3
    assert res["pages"][0]["page_number"] == 1
    assert res["pages"][1]["page_number"] == 2
    assert res["pages"][2]["page_number"] == 3
    assert "Introduction" in res["pages"][0]["text"]
    assert "Architecture" in res["pages"][1]["text"]
    assert "Conclusion" in res["pages"][2]["text"]


def test_extract_pdf_with_empty_page(pdf_service: PDFProcessingService) -> None:
    # Page 1 has text, Page 2 is blank, Page 3 has text
    pdf_bytes = _create_sample_pdf_bytes(["Content on Page 1", "", "Content on Page 3"])
    res = pdf_service.extract_text_from_bytes(pdf_bytes, filename="empty_page.pdf")

    assert res["total_pages"] == 3
    assert res["pages"][0]["text"] == "Content on Page 1"
    assert res["pages"][1]["text"] == ""  # Gracefully handled blank page
    assert res["pages"][2]["text"] == "Content on Page 3"


def test_invalid_file_header_raises_validation_error(pdf_service: PDFProcessingService) -> None:
    invalid_bytes = b"This is plain text, not a PDF file."
    with pytest.raises(PDFValidationError, match="invalid magic header"):
        pdf_service.extract_text_from_bytes(invalid_bytes, filename="fake.pdf")



def test_no_usable_text_raises_extraction_error(pdf_service: PDFProcessingService) -> None:
    # PDF with completely blank pages (simulating image-only or blank PDF)
    blank_pdf_bytes = _create_sample_pdf_bytes(["", ""])
    with pytest.raises(PDFProcessingError, match="contains no usable text"):
        pdf_service.extract_text_from_bytes(blank_pdf_bytes, filename="blank.pdf")
