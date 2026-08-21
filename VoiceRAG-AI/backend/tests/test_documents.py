import pytest
from httpx import AsyncClient


async def test_upload_single_pdf(client: AsyncClient, sample_pdf: bytes) -> None:
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "test.pdf"
    assert body["status"] == "completed"
    assert body["total_chunks"] > 0
    assert "document_id" in body


async def test_upload_multiple_pdfs(client: AsyncClient, sample_pdf: bytes) -> None:
    pdf2 = sample_pdf[:-1] + b"X"
    res1 = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("a.pdf", sample_pdf, "application/pdf")},
    )
    assert res1.status_code == 201

    res2 = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("b.pdf", pdf2, "application/pdf")},
    )
    assert res2.status_code == 201


async def test_rejects_non_pdf_mime(client: AsyncClient, sample_pdf: bytes) -> None:
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", sample_pdf, "text/plain")},
    )
    assert response.status_code in (400, 422)


async def test_rejects_wrong_extension(client: AsyncClient, sample_pdf: bytes) -> None:
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", sample_pdf, "application/pdf")},
    )
    assert response.status_code in (400, 422)


async def test_rejects_empty_file(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code in (400, 422)


async def test_rejects_invalid_header(client: AsyncClient) -> None:
    invalid_content = b"NOT_A_PDF_CONTENT_HEADER"
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("invalid.pdf", invalid_content, "application/pdf")},
    )
    assert response.status_code in (400, 422)


async def test_list_documents(client: AsyncClient, sample_pdf: bytes) -> None:
    await client.post(
        "/api/v1/documents/upload",
        files={"file": ("list_test.pdf", sample_pdf, "application/pdf")},
    )
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert isinstance(body["documents"], list)


async def test_delete_document(client: AsyncClient, sample_pdf: bytes) -> None:
    upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("del_test.pdf", sample_pdf, "application/pdf")},
    )
    doc_id = upload.json()["document_id"]

    response = await client.delete(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200


async def test_delete_nonexistent_returns_404(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/documents/nonexistent-id")
    assert response.status_code == 404


async def test_get_document_file_success(client: AsyncClient, sample_pdf: bytes) -> None:
    upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("file_test.pdf", sample_pdf, "application/pdf")},
    )
    doc_id = upload.json()["document_id"]

    response = await client.get(f"/api/v1/documents/{doc_id}/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == sample_pdf


async def test_get_document_file_nonexistent_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/documents/nonexistent-doc-id/file")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"


async def test_get_document_file_path_traversal_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/documents/..%2F..%2Fetc%2Fpasswd/file")
    assert response.status_code == 404

