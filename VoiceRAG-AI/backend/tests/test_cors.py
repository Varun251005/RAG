"""
Unit and integration test suite for CORS configuration and CORSMiddleware.
"""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import create_app


class TestCORSConfig:
    def test_default_allowed_origins(self) -> None:
        settings = Settings()
        assert "http://localhost:3000" in settings.allowed_origins

    def test_single_origin_string_parsing(self) -> None:
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://localhost:3000"}):
            settings = Settings()
            assert settings.allowed_origins == ["http://localhost:3000"]

    def test_multiple_comma_separated_origins_parsing(self) -> None:
        raw_origins = "http://localhost:3000, http://localhost:3001, https://app.voicerag.ai"
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": raw_origins}):
            settings = Settings()
            assert settings.allowed_origins == [
                "http://localhost:3000",
                "http://localhost:3001",
                "https://app.voicerag.ai",
            ]

    def test_json_array_origins_parsing(self) -> None:
        json_origins = '["http://localhost:3000", "https://app.voicerag.ai"]'
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": json_origins}):
            settings = Settings()
            assert settings.allowed_origins == [
                "http://localhost:3000",
                "https://app.voicerag.ai",
            ]


class TestCORSMiddleware:
    @pytest.mark.asyncio
    async def test_cors_allowed_origin_header(self) -> None:
        test_app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as client:
            headers = {"Origin": "http://localhost:3000"}
            response = await client.get("/api/v1/health", headers=headers)
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
            assert response.headers.get("access-control-allow-credentials") == "true"

    @pytest.mark.asyncio
    async def test_cors_preflight_options_request(self) -> None:
        test_app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as client:
            headers = {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            }
            response = await client.options("/api/v1/health", headers=headers)
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    @pytest.mark.asyncio
    async def test_cors_disallowed_origin_rejected(self) -> None:
        test_app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as client:
            headers = {"Origin": "http://unauthorized-domain.com"}
            response = await client.get("/api/v1/health", headers=headers)
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") != "http://unauthorized-domain.com"
