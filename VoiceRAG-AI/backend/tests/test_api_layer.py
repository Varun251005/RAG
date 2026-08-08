"""
Integration test suite for FastAPI HTTP API endpoints:
- POST /api/v1/documents/upload
- GET  /api/v1/documents
- GET  /api/v1/documents/{document_id}
- DELETE /api/v1/documents/{document_id}
- POST /api/v1/chat
"""

from __future__ import annotations

import json
import fitz
import pytest
from pathlib import Path
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
    vector_svc = VectorStoreService(default_collection="test_api_voicerag")
    vector_svc._client = chromadb.EphemeralClient()

    app.dependency_overrides[get_vector_store_service] = lambda: vector_svc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_full_api_suite(async_client: AsyncClient) -> None:
    results = {}

    # 1. PDF Upload & Ingestion
    pdf_bytes = _create_sample_pdf_bytes("Python is an interpreted high-level general-purpose programming language.")
    files = {"file": ("python_intro.pdf", pdf_bytes, "application/pdf")}

    up_res = await async_client.post("/api/v1/documents/upload", files=files)
    assert up_res.status_code == 201
    up_data = up_res.json()
    doc_id = up_data["document_id"]
    results["upload"] = {"status_code": up_res.status_code, "response": up_data}

    # 2. Invalid File Upload
    inv_files = {"file": ("bad.txt", b"invalid header", "text/plain")}
    inv_res = await async_client.post("/api/v1/documents/upload", files=inv_files)
    assert inv_res.status_code == 422
    results["invalid_upload"] = {"status_code": inv_res.status_code}

    # 3. List Documents
    list_res = await async_client.get("/api/v1/documents")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    results["list"] = {"status_code": list_res.status_code, "response": list_data}

    # 4. Get Document
    get_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["document_id"] == doc_id
    results["get"] = {"status_code": get_res.status_code, "response": get_data}

    # 5. Nonexistent Document
    non_res = await async_client.get("/api/v1/documents/nonexistent_123")
    assert non_res.status_code == 404
    results["nonexistent"] = {"status_code": non_res.status_code}

    # 6. Chat Query with document_id
    chat_req = {"question": "What is Python?", "document_id": doc_id}
    chat_res = await async_client.post("/api/v1/chat", json=chat_req)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "answer" in chat_data
    assert len(chat_data["sources"]) > 0
    results["chat"] = {"status_code": chat_res.status_code, "response": chat_data}

    # 7. Chat Query with empty question
    empty_chat_res = await async_client.post("/api/v1/chat", json={"question": "  "})
    assert empty_chat_res.status_code == 422
    results["empty_chat"] = {"status_code": empty_chat_res.status_code}

    # 8. Delete Document
    del_res = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
    results["delete"] = {"status_code": del_res.status_code, "response": del_res.json()}

    # Verify document deleted
    get_del_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_del_res.status_code == 404

    Path("api_layer_test_report.json").write_text(json.dumps(results, indent=2))
