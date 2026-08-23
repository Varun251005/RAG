"""Unit and integration tests for audio speech-to-text transcription (Phase 10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

import app.api.deps as deps
from app.core.exceptions import UnprocessableError
from app.models.transcription import TranscriptionResponse
from app.services.transcription_service import TranscriptionService


class TestTranscriptionService:
    async def test_transcribe_audio_success(self) -> None:
        svc = TranscriptionService(api_key="fake-key")
        svc._transcribe_with_gemini = AsyncMock(return_value="What is the total revenue?")  # type: ignore[method-assign]

        fake_audio = b"RIFF" + b"\x00" * 200
        res = await svc.transcribe_audio(fake_audio, mime_type="audio/webm")

        assert isinstance(res, TranscriptionResponse)
        assert res.text == "What is the total revenue?"
        assert res.confidence > 0.0

    async def test_transcribe_empty_audio_raises_unprocessable(self) -> None:
        svc = TranscriptionService(api_key="fake-key")
        with pytest.raises(UnprocessableError):
            await svc.transcribe_audio(b"")


class TestAudioAPI:
    @pytest.fixture(autouse=True)
    def inject_mock_transcription_service(self) -> None:
        mock_svc = MagicMock()
        mock_svc.transcribe_audio = AsyncMock(
            return_value=TranscriptionResponse(
                text="Hello world test transcription",
                language="en",
                duration_seconds=2.5,
                confidence=0.96,
            )
        )
        deps._transcription_service = mock_svc

    async def test_transcribe_endpoint_200(self, client) -> None:
        fake_webm = b"HEADER" + b"\x00" * 200
        response = await client.post(
            "/api/v1/audio/transcribe",
            files={"file": ("recording.webm", fake_webm, "audio/webm")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["text"] == "Hello world test transcription"
        assert body["language"] == "en"
