"""
Chunking service — splits PDF documents into overlapping text chunks.

Usage
-----
    from app.services.chunking_service import ChunkingService

    service = ChunkingService()                         # uses config defaults
    result  = await service.chunk_document(doc_id, pdf_bytes, "report.pdf")

    for chunk in result.chunks:
        print(chunk.chunk_id, chunk.metadata.page_number, chunk.text[:80])

Configuration
-------------
All tuneable knobs live in ``app.core.config.Settings``:

    CHUNK_SIZE          — target character count per chunk  (default 1 000)
    CHUNK_OVERLAP       — overlap between consecutive chunks (default 200)

Algorithm
---------
1. Parse the PDF with *pypdf* page-by-page to preserve page numbers.
2. Feed each page's text + page metadata into
   ``langchain_text_splitters.RecursiveCharacterTextSplitter``.
3. Assign a deterministic ``chunk_id`` of the form
   ``<doc_id>_p<page>_c<seq_within_page>``.
4. Return a ``ChunkingResult`` containing every ``DocumentChunk``.

The splitter is re-used across calls (stateless) so instantiation cost is
paid only once.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.exceptions import ServiceError, UnprocessableError
from app.models.chunk import ChunkMetadata, ChunkingResult, DocumentChunk


class ChunkingService:
    """
    Stateless service that converts a raw PDF (bytes or path) into
    ``DocumentChunk`` objects using ``RecursiveCharacterTextSplitter``.

    Parameters
    ----------
    chunk_size : int
        Maximum number of characters per chunk.  Defaults to ``Settings.chunk_size``.
    chunk_overlap : int
        Character overlap between consecutive chunks.
        Defaults to ``Settings.chunk_overlap``.

    Notes
    -----
    * The instance holds a single ``RecursiveCharacterTextSplitter`` that is
      safe to share across async tasks (LangChain splitters are stateless).
    * Empty pages are silently skipped; a warning is logged if an entire
      document yields no text.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        cfg = get_settings()
        self._chunk_size: int = chunk_size if chunk_size is not None else cfg.chunk_size
        self._chunk_overlap: int = (
            chunk_overlap if chunk_overlap is not None else cfg.chunk_overlap
        )

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            # Prefer paragraph > sentence > word boundaries in that order.
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )
        logger.debug(
            f"ChunkingService initialised | "
            f"chunk_size={self._chunk_size} | chunk_overlap={self._chunk_overlap}"
        )

    # ── Public interface ───────────────────────────────────────────────────────

    async def chunk_document(
        self,
        document_id: str,
        pdf_content: bytes,
        original_filename: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> ChunkingResult:
        """
        Parse *pdf_content* and split it into overlapping text chunks.

        Parameters
        ----------
        document_id :
            UUID string of the parent ``DocumentRecord`` — embedded in every
            ``ChunkMetadata`` and used to build deterministic chunk IDs.
        pdf_content :
            Raw PDF bytes.
        original_filename :
            Human-readable name propagated into ``ChunkMetadata``.
        extra_metadata :
            Optional additional key/value pairs (e.g. author, title) stored
            in ``ChunkMetadata.extra``.

        Returns
        -------
        ChunkingResult
            Contains ``document_id``, ``total_chunks``, and the list of
            ``DocumentChunk`` objects.

        Raises
        ------
        UnprocessableError
            If the PDF cannot be parsed.
        ServiceError
            If an unexpected error occurs during chunking.
        """
        pages = self._extract_pages(pdf_content, document_id)
        total_pages = len(pages)

        chunks: list[DocumentChunk] = []
        global_index = 0

        for page_number, page_text in pages:
            page_chunks = self._split_page(
                page_text=page_text,
                document_id=document_id,
                page_number=page_number,
                total_pages=total_pages,
                original_filename=original_filename,
                extra_metadata=extra_metadata or {},
                global_index_start=global_index,
            )
            chunks.extend(page_chunks)
            global_index += len(page_chunks)

        if not chunks:
            logger.warning(
                f"Document yielded no text chunks | id={document_id} | "
                f"filename={original_filename}"
            )

        logger.info(
            f"Chunking complete | id={document_id} | "
            f"pages={total_pages} | chunks={len(chunks)}"
        )
        return ChunkingResult(
            document_id=document_id,
            total_chunks=len(chunks),
            chunks=chunks,
        )

    async def chunk_document_from_path(
        self,
        document_id: str,
        pdf_path: Path,
        original_filename: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> ChunkingResult:
        """
        Convenience wrapper — reads *pdf_path* from disk then delegates to
        :meth:`chunk_document`.
        """
        try:
            pdf_content = pdf_path.read_bytes()
        except OSError as exc:
            logger.error(f"Cannot read PDF | path={pdf_path} | error={exc}")
            raise ServiceError(f"Cannot read PDF file: {exc}") from exc

        return await self.chunk_document(
            document_id=document_id,
            pdf_content=pdf_content,
            original_filename=original_filename,
            extra_metadata=extra_metadata,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _extract_pages(
        self, pdf_content: bytes, document_id: str
    ) -> list[tuple[int, str]]:
        """
        Parse *pdf_content* and return ``[(page_number_1_indexed, text), …]``.

        Empty pages are filtered out so the splitter never receives blank input.
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
        except Exception as exc:
            logger.error(f"PDF parse error | id={document_id} | error={exc}")
            raise UnprocessableError(
                f"Could not parse PDF '{document_id}': {exc}"
            ) from exc

        pages: list[tuple[int, str]] = []
        for page_index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((page_index, text))
            else:
                logger.debug(
                    f"Skipping empty page | id={document_id} | page={page_index}"
                )

        return pages

    def _split_page(
        self,
        *,
        page_text: str,
        document_id: str,
        page_number: int,
        total_pages: int,
        original_filename: str,
        extra_metadata: dict[str, Any],
        global_index_start: int,
    ) -> list[DocumentChunk]:
        """
        Split a single page's text into chunks and attach rich metadata.

        Chunk IDs follow the pattern:
            ``<document_id>_p<page_number>_c<chunk_within_page>``
        """
        raw_chunks: list[str] = self._splitter.split_text(page_text)

        metadata = ChunkMetadata(
            document_id=document_id,
            original_filename=original_filename,
            page_number=page_number,
            total_pages=total_pages,
            extra=extra_metadata,
        )

        result: list[DocumentChunk] = []
        for within_page_index, text in enumerate(raw_chunks):
            chunk_id = f"{document_id}_p{page_number:04d}_c{within_page_index:04d}"
            result.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    chunk_index=global_index_start + within_page_index,
                    text=text,
                    metadata=metadata,
                )
            )
        return result
