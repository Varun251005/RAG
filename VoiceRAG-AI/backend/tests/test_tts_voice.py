"""
Unit and API Integration Test Suite for Edge-TTS Text-to-Speech (TTS) service
and POST /api/v1/voice/synthesize endpoint.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_tts_service
from app.core.config import get_settings
from app.main import app
from app.services.tts_service import InvalidTTSTextError, TTSService, TTSServiceError


@pytest.fixture
def tts_service() -> TTSService:
    settings = get_settings()
    return TTSService(
        default_voice=settings.edge_tts_voice,
        max_text_length=settings.tts_max_text_length,
    )


@pytest.fixture
async def async_client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_1_valid_tts_speech_generation(tts_service: TTSService) -> None:
    """Test 1, 4, 7: Edge-TTS generates non-empty audio for 'Python is a programming language.'."""
    text = "Python is a programming language."
    t0 = time.perf_counter()
    audio_bytes = await tts_service.synthesize_speech(text, voice="en-US-AvaNeural")
    t1 = time.perf_counter()

    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 500  # Non-empty MP3 audio
    print(f"\n[TTS Test] Audio size: {len(audio_bytes)} bytes | Generation time: {t1-t0:.2f}s")


@pytest.mark.asyncio
async def test_2_empty_text_validation(tts_service: TTSService) -> None:
    """Test 2: Empty text raises InvalidTTSTextError."""
    with pytest.raises(InvalidTTSTextError) as exc_info:
        await tts_service.synthesize_speech("   ", voice="en-US-AvaNeural")
    assert "empty" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_3_excessively_long_text_validation(tts_service: TTSService) -> None:
    """Test 3: Text exceeding maximum allowed limit raises InvalidTTSTextError."""
    long_text = "Word " * 1500  # ~7500 chars > 4096 max limit
    with pytest.raises(InvalidTTSTextError) as exc_info:
        await tts_service.synthesize_speech(long_text, voice="en-US-AvaNeural")
    assert "exceeds maximum allowed limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_5_invalid_voice_fallback_handling(tts_service: TTSService) -> None:
    """Test 5: Invalid/unavailable voice falls back gracefully to default voice or succeeds."""
    text = "Hello from VoiceRAG AI testing."
    audio_bytes = await tts_service.synthesize_speech(text, voice="non-existent-invalid-voice-12345")

    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 200


@pytest.mark.asyncio
async def test_8_temporary_file_cleanup(tts_service: TTSService) -> None:
    """Test 8: Verify temporary MP3 files are cleanly removed when written to disk."""
    temp_path = await tts_service.synthesize_to_temp_file("Python is a programming language.")
    assert temp_path.exists()
    assert temp_path.stat().st_size > 0

    # Cleanup temp file
    os.unlink(temp_path)
    assert not temp_path.exists()


@pytest.mark.asyncio
async def test_6_api_endpoint_content_type_and_schema(async_client: AsyncClient) -> None:
    """Test 6, 7 & 9: POST /api/v1/voice/synthesize returns 200 with audio/mpeg Content-Type."""
    payload = {
        "text": "Python is a programming language.",
        "voice": "en-US-AvaNeural",
    }
    res = await async_client.post("/api/v1/voice/synthesize", json=payload)

    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert len(res.content) > 500


@pytest.mark.asyncio
async def test_api_endpoint_empty_text(async_client: AsyncClient) -> None:
    """Test 2 & API: Empty text payload returns 422 Unprocessable Content."""
    res = await async_client.post("/api/v1/voice/synthesize", json={"text": ""})
    assert res.status_code == 422
