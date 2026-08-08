"""
Unit tests for ChunkingService.

Tests use a minimal synthetic PDF built with pypdf so they have no external
file dependency and run entirely in-memory.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from app.models.chunk import ChunkMetadata, ChunkingResult, DocumentChunk
from app.services.chunking_service import ChunkingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf(pages: list[str]) -> bytes:
    """Return minimal in-memory PDF bytes with one text page per string."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        # pypdf PdfWriter doesn't embed fonts for text; for testing we inject
        # the text through the underlying content stream so extract_text works.
        page.merge_page(page)  # no-op merge keeps the page valid
        # Write raw content stream so extract_text returns the text back.
        page["/Contents"] = writer._add_object(  # type: ignore[attr-defined]
            io.BytesIO(
                f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode()
            )
        )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _real_pdf(text_per_page: list[str]) -> bytes:
    """
    Build a proper PDF using reportlab (if available) or fall back to a
    hand-crafted minimal PDF that pypdf can extract text from.
    """
    try:
        from reportlab.lib.pagesizes import LETTER  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=LETTER)
        for text in text_per_page:
            c.drawString(50, 700, text)
            c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()
    except ImportError:
        pass

    # Minimal hand-crafted PDF — works with pypdf text extraction.
    pages_objs: list[str] = []
    obj_offset = 1  # object 1 = catalog, 2 = pages, 3..N = page+stream pairs

    streams: list[tuple[str, str]] = []
    for i, text in enumerate(text_per_page):
        escaped = text.replace("(", r"\(").replace(")", r"\)")
        stream_content = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET"
        streams.append((f"page_{i}", stream_content))

    lines: list[str] = [
        "%PDF-1.4",
    ]

    xref: list[int] = []

    def emit(obj_lines: list[str]) -> int:
        xref.append(sum(len(l) + 1 for l in lines))
        lines.extend(obj_lines)
        return len(xref)  # 1-indexed object number

    # Build one content stream + page per text entry
    page_ids: list[int] = []
    stream_ids: list[int] = []
    for text in text_per_page:
        escaped = text.replace("(", r"\(").replace(")", r"\)")
        stream_body = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET"
        sb = stream_body.encode()
        sid = emit(
            [
                f"{len(xref) + 1} 0 obj",
                f"<< /Length {len(sb)} >>",
                "stream",
                stream_body,
                "endstream",
                "endobj",
                "",
            ]
        )
        stream_ids.append(sid)

    pages_obj_id = len(xref) + 1 + len(text_per_page)  # placeholder
    for i, text in enumerate(text_per_page):
        pid = emit(
            [
                f"{len(xref) + 1} 0 obj",
                "<< /Type /Page",
                f"   /Parent {pages_obj_id} 0 R",
                f"   /MediaBox [0 0 612 792]",
                f"   /Contents {stream_ids[i]} 0 R",
                f"   /Resources << /Font << /F1 << /Type /Font /Subtype /Type1"
                f" /BaseFont /Helvetica >> >> >>",
                ">>",
                "endobj",
                "",
            ]
        )
        page_ids.append(pid)

    pages_list = " ".join(f"{p} 0 R" for p in page_ids)
    pages_id = emit(
        [
            f"{len(xref) + 1} 0 obj",
            "<< /Type /Pages",
            f"   /Kids [{pages_list}]",
            f"   /Count {len(page_ids)}",
            ">>",
            "endobj",
            "",
        ]
    )

    catalog_id = emit(
        [
            f"{len(xref) + 1} 0 obj",
            "<< /Type /Catalog",
            f"   /Pages {pages_id} 0 R",
            ">>",
            "endobj",
            "",
        ]
    )

    startxref = sum(len(l) + 1 for l in lines)
    lines.append("xref")
    lines.append(f"0 {len(xref) + 1}")
    lines.append("0000000000 65535 f ")
    for off in xref:
        lines.append(f"{off:010d} 00000 n ")

    lines += [
        "trailer",
        f"<< /Size {len(xref) + 1} /Root {catalog_id} 0 R >>",
        "startxref",
        str(startxref),
        "%%EOF",
    ]

    return "\n".join(lines).encode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DOC_ID = "test-doc-uuid-1234"
FILENAME = "sample.pdf"

LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris. "
) * 10  # ~1 400 chars → will produce multiple chunks with size=1000


@pytest.fixture()
def service() -> ChunkingService:
    return ChunkingService(chunk_size=1000, chunk_overlap=200)


@pytest.fixture()
def single_page_pdf() -> bytes:
    return _real_pdf([LOREM])


@pytest.fixture()
def two_page_pdf() -> bytes:
    return _real_pdf([LOREM, LOREM])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChunkingServiceInit:
    def test_defaults_come_from_config(self) -> None:
        svc = ChunkingService()
        assert svc._chunk_size == 1000
        assert svc._chunk_overlap == 200

    def test_explicit_override(self) -> None:
        svc = ChunkingService(chunk_size=500, chunk_overlap=50)
        assert svc._chunk_size == 500
        assert svc._chunk_overlap == 50


class TestChunkDocumentStructure:
    async def test_returns_chunking_result(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        assert isinstance(result, ChunkingResult)
        assert result.document_id == DOC_ID
        assert result.total_chunks == len(result.chunks)

    async def test_chunks_are_non_empty(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        for chunk in result.chunks:
            assert chunk.text.strip(), "Chunk text must not be blank"

    async def test_chunk_index_is_sequential(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        indices = [c.chunk_index for c in result.chunks]
        assert indices == list(range(len(result.chunks)))

    async def test_chunk_ids_are_unique(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        ids = [c.chunk_id for c in result.chunks]
        assert len(ids) == len(set(ids)), "All chunk IDs must be unique"

    async def test_chunk_id_format(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        first = result.chunks[0]
        # Expected: <doc_id>_p0001_c0000
        assert first.chunk_id.startswith(f"{DOC_ID}_p"), (
            f"Unexpected chunk_id prefix: {first.chunk_id}"
        )
        parts = first.chunk_id.split("_")
        assert any(p.startswith("p") and p[1:].isdigit() for p in parts)
        assert any(p.startswith("c") and p[1:].isdigit() for p in parts)


class TestMetadataPreservation:
    async def test_page_number_preserved(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        for chunk in result.chunks:
            assert chunk.metadata.page_number >= 1

    async def test_total_pages_preserved(
        self, service: ChunkingService, two_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, two_page_pdf, FILENAME)
        for chunk in result.chunks:
            assert chunk.metadata.total_pages == 2

    async def test_document_id_in_metadata(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        for chunk in result.chunks:
            assert chunk.metadata.document_id == DOC_ID

    async def test_original_filename_in_metadata(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        for chunk in result.chunks:
            assert chunk.metadata.original_filename == FILENAME

    async def test_extra_metadata_propagated(
        self, service: ChunkingService, single_page_pdf: bytes
    ) -> None:
        extra = {"author": "Alice", "subject": "Testing"}
        result = await service.chunk_document(
            DOC_ID, single_page_pdf, FILENAME, extra_metadata=extra
        )
        for chunk in result.chunks:
            assert chunk.metadata.extra == extra


class TestMultiPage:
    async def test_two_page_doc_has_both_pages(
        self, service: ChunkingService, two_page_pdf: bytes
    ) -> None:
        result = await service.chunk_document(DOC_ID, two_page_pdf, FILENAME)
        page_numbers = {c.metadata.page_number for c in result.chunks}
        assert 1 in page_numbers
        assert 2 in page_numbers

    async def test_chunk_count_increases_with_pages(
        self, service: ChunkingService, single_page_pdf: bytes, two_page_pdf: bytes
    ) -> None:
        r1 = await service.chunk_document(DOC_ID, single_page_pdf, FILENAME)
        r2 = await service.chunk_document(DOC_ID, two_page_pdf, FILENAME)
        assert r2.total_chunks > r1.total_chunks


class TestPathEntryPoint:
    async def test_chunk_from_path(
        self, service: ChunkingService, single_page_pdf: bytes, tmp_path: Path
    ) -> None:
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(single_page_pdf)
        result = await service.chunk_document_from_path(DOC_ID, pdf_path, FILENAME)
        assert result.total_chunks > 0

    async def test_missing_path_raises_service_error(
        self, service: ChunkingService, tmp_path: Path
    ) -> None:
        from app.core.exceptions import ServiceError

        missing = tmp_path / "nonexistent.pdf"
        with pytest.raises(ServiceError):
            await service.chunk_document_from_path(DOC_ID, missing, FILENAME)
