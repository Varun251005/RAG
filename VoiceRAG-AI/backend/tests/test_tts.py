"""Unit and API integration tests for Text-to-Speech audio generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.tts_service import TTSService, InvalidTTSTextError


class TestTTSService:
    def test_default_voice_configured(self) -> None:
        svc = TTSService()
        assert svc.default_voice == "en-US-AvaNeural"
        assert svc.max_text_length == 4096

    def test_clean_text_for_speech(self) -> None:
        svc = TTSService()
        raw = "# Hello World\n```python\nprint('code')\n```\nCheck out [link](http://example.com) and **bold** text."
        cleaned = svc._clean_text_for_speech(raw)
        assert "Hello World" in cleaned
        assert "bold" in cleaned
        assert "```" not in cleaned

    def test_validate_text(self) -> None:
        svc = TTSService()
        valid = svc.validate_text("Hello this is a valid text")
        assert valid == "Hello this is a valid text"

        with pytest.raises(InvalidTTSTextError):
            svc.validate_text("   ")


class TestTTSAPI:
    async def test_tts_synthesize_endpoint(self, client) -> None:
        response = await client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Hello world text to speech stream", "voice": "en-US-AvaNeural"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        content = response.content
        assert len(content) > 0
