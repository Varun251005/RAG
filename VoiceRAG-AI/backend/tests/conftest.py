"""
Shared pytest fixtures for the VoiceRAG AI backend test suite.

Fixtures
--------
reset_document_service (autouse)
    Replaces the global DocumentService singleton with a fresh instance
    pointing at a temporary directory before every test, then tears it down.

reset_vector_store_service (autouse)
    Replaces the global VectorStoreService singleton with None before every
    test so each test that needs it can inject its own mock.

client
    Async HTTP client wired directly to the ASGI app via httpx.ASGITransport.

sample_pdf
    Minimal valid PDF bytes for upload tests.
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.deps as deps


@pytest.fixture(autouse=True)
def reset_document_service(tmp_path: Path) -> None:
    """
    Reset the singleton DocumentService before each test and point it at
    a temporary directory so tests are fully isolated from each other.
    """
    from app.services.document_service import DocumentService

    deps._document_service = DocumentService(
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=25 * 1024 * 1024,
    )
    yield
    deps._document_service = None


@pytest.fixture(autouse=True)
def reset_vector_store_service() -> None:
    """
    Initialise the VectorStoreService singleton with an EphemeralClient before each test.
    """
    import chromadb
    from app.services.vector_store_service import VectorStoreService

    svc = VectorStoreService()
    svc._client = chromadb.EphemeralClient()
    deps._vector_store_service = svc
    yield
    deps._vector_store_service = None


@pytest.fixture(autouse=True)
def reset_rag_service() -> None:
    """
    Clear the RAGService singleton before and after every test.

    Tests inject a mock via ``deps._rag_service = <mock>``.
    """
    deps._rag_service = None
    yield
    deps._rag_service = None


@pytest.fixture(autouse=True)
def reset_transcription_service() -> None:
    """
    Clear the TranscriptionService singleton before and after every test.

    Tests inject a mock via ``deps._transcription_service = <mock>``.
    """
    deps._transcription_service = None
    yield
    deps._transcription_service = None


@pytest.fixture(autouse=True)
def reset_tts_service() -> None:
    """
    Clear the TTSService singleton before and after every test.

    Tests inject a mock via ``deps._tts_service = <mock>``.
    """
    deps._tts_service = None
    yield
    deps._tts_service = None


@pytest.fixture(autouse=True)
def reset_bm25_service() -> None:
    """Clear the BM25Service singleton before and after every test."""
    deps._bm25_service = None
    yield
    deps._bm25_service = None


@pytest.fixture(autouse=True)
def reset_reranker_service() -> None:
    """Clear the RerankerService singleton before and after every test."""
    deps._reranker_service = None
    yield
    deps._reranker_service = None



@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired directly to the ASGI app."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def sample_pdf() -> bytes:
    """Minimal valid PDF binary with text for upload & ingestion tests."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Sample test PDF content for VoiceRAG AI testing.", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
