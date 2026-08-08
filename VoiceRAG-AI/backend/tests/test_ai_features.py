"""Unit and API tests for Document AI Features (Phase 14)."""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest

import app.api.deps as deps
from app.models.rag import RAGResponse, RAGSource


class TestAIFeaturesAPI:
    @pytest.fixture(autouse=True)
    def inject_mock_rag_service(self) -> None:
        mock_svc = AsyncMock()
        mock_svc.generate_ai_feature.return_value = RAGResponse(
            question="Provide a summary",
            answer="# Executive Summary\n- Key point 1\n- Key point 2",
            sources=[
                RAGSource(
                    chunk_id="chunk1",
                    snippet="Sample content snippet",
                    page_number=1,
                    original_filename="doc.pdf",
                    score=0.92,
                    document_id="doc123",
                )
            ],
            total_chunks_used=1,
            model="gemini-2.0-flash",
        )
        deps._rag_service = mock_svc

    async def test_ai_features_endpoint(self, client) -> None:
        response = await client.post(
            "/api/v1/rag/ai-features",
            json={"document_id": "doc123", "feature": "summary"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "Executive Summary" in body["answer"]
        assert len(body["sources"]) == 1
