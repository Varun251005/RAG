"""
End-to-End Frontend-to-Backend Chat Integration Test Suite:
Tests all 5 required verification flows for VoiceRAG AI RAG Chat endpoint.
"""

from __future__ import annotations

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

import chromadb
from app.api.deps import get_vector_store_service
from app.main import app
from app.services.vector_store_service import VectorStoreService


def _create_sample_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
async def async_client() -> AsyncClient:
    vector_svc = VectorStoreService(default_collection="test_chat_integration")
    vector_svc._client = chromadb.EphemeralClient()

    app.dependency_overrides[get_vector_store_service] = lambda: vector_svc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_1_upload_and_chat_query(async_client: AsyncClient) -> None:
    """Test 1: Upload PDF about Python and ask 'What is Python used for?'"""
    pdf_text = "Python is a popular programming language used for web development, data analysis, and artificial intelligence."
    pdf_bytes = _create_sample_pdf_bytes(pdf_text)
    files = {"file": ("python_info.pdf", pdf_bytes, "application/pdf")}

    upload_res = await async_client.post("/api/v1/documents/upload", files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document_id"]

    # Chat query
    chat_payload = {"question": "What is Python used for?", "document_id": doc_id}
    chat_res = await async_client.post("/api/v1/chat", json=chat_payload)

    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "answer" in data
    assert len(data["sources"]) > 0
    source = data["sources"][0]
    assert source["filename"] == "python_info.pdf"
    assert source["page_number"] == 1
    assert source["document_id"] == doc_id


@pytest.mark.asyncio
async def test_2_filter_by_document_id(async_client: AsyncClient) -> None:
    """Test 2: Ask a question with specific document_id filter."""
    pdf_bytes = _create_sample_pdf_bytes("FastAPI is a modern web framework for building APIs with Python.")
    upload_res = await async_client.post("/api/v1/documents/upload", files={"file": ("fastapi.pdf", pdf_bytes, "application/pdf")})
    doc_id = upload_res.json()["document_id"]

    chat_payload = {"question": "What is FastAPI?", "document_id": doc_id}
    chat_res = await async_client.post("/api/v1/chat", json=chat_payload)

    assert chat_res.status_code == 200
    data = chat_res.json()
    assert len(data["sources"]) > 0
    assert data["sources"][0]["document_id"] == doc_id


@pytest.mark.asyncio
async def test_3_clear_document_filter(async_client: AsyncClient) -> None:
    """Test 3: Ask question across all documents with document_id: null."""
    pdf_bytes = _create_sample_pdf_bytes("Machine learning relies on statistical algorithms.")
    await async_client.post("/api/v1/documents/upload", files={"file": ("ml.pdf", pdf_bytes, "application/pdf")})

    chat_payload = {"question": "What does machine learning rely on?", "document_id": None}
    chat_res = await async_client.post("/api/v1/chat", json=chat_payload)

    assert chat_res.status_code == 200
    data = chat_res.json()
    assert len(data["sources"]) > 0


@pytest.mark.asyncio
async def test_4_unanswerable_question(async_client: AsyncClient) -> None:
    """Test 4: Ask a question not in indexed documents."""
    chat_payload = {"question": "What is the secret recipe for quantum gravitational warp propulsion?"}
    chat_res = await async_client.post("/api/v1/chat", json=chat_payload)

    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "answer" in data
    # Answer should state information is unavailable or provide grounded refusal


@pytest.mark.asyncio
async def test_5_empty_input_validation(async_client: AsyncClient) -> None:
    """Test 5: Empty input validation returns 422 Unprocessable Content."""
    res = await async_client.post("/api/v1/chat", json={"question": "   "})
    assert res.status_code == 422
