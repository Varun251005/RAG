"""
Unit and API integration test suite for Faster-Whisper Speech-to-Text (STT) service
and POST /api/v1/voice/transcribe endpoint.
"""

from __future__ import annotations

import io
import math
import os
import struct
import wave
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_stt_service
from app.core.config import get_settings
from app.main import app
from app.services.stt_service import InvalidAudioError, STTService, STTServiceError


def create_sample_wav_bytes(duration_sec: float = 1.5, freq: float = 440.0, sample_rate: int = 16000) -> bytes:
    """Generate a clean PCM 16-bit mono WAV audio byte stream for testing."""
    buf = io.BytesIO()
    num_samples = int(sample_rate * duration_sec)
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(num_samples):
            sample_val = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * freq * i / sample_rate))
            wav_file.writeframes(struct.pack("<h", sample_val))
    return buf.getvalue()


@pytest.fixture
def stt_service() -> STTService:
    settings = get_settings()
    return STTService(
        model_size=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


@pytest.fixture
async def async_client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


def test_stt_model_loading_and_cpu_config(stt_service: STTService) -> None:
    """Test 7 & 6: Verify model size, compute type, and CPU execution configuration."""
    assert stt_service.model_size == "tiny"
    assert stt_service.device == "cpu"
    assert stt_service.compute_type in {"int8", "float32"}

    model = stt_service._get_model()
    assert model is not None


def test_stt_valid_audio_transcription_and_language(stt_service: STTService) -> None:
    """Test 1 & 5: Valid audio transcription, duration, and language detection."""
    wav_bytes = create_sample_wav_bytes(duration_sec=1.5)
    t0 = time.perf_counter()
    result = stt_service.transcribe_audio_bytes(wav_bytes, filename="test_sample.wav")
    t1 = time.perf_counter()

    assert "text" in result
    assert "language" in result
    assert "duration" in result
    assert isinstance(result["duration"], float)
    assert result["duration"] > 0.5
    assert isinstance(result["language"], str)


def test_stt_empty_audio_validation(stt_service: STTService) -> None:
    """Test 2: Empty audio file raises InvalidAudioError."""
    with pytest.raises(InvalidAudioError) as exc_info:
        stt_service.transcribe_audio_bytes(b"", filename="empty.wav")
    assert "empty" in str(exc_info.value).lower()


def test_stt_unsupported_format(stt_service: STTService) -> None:
    """Test 4: Unsupported format (e.g. .txt / .pdf) raises InvalidAudioError."""
    with pytest.raises(InvalidAudioError) as exc_info:
        stt_service.transcribe_audio_bytes(b"some text data", filename="document.txt")
    assert "unsupported" in str(exc_info.value).lower()


def test_stt_temporary_file_cleanup(stt_service: STTService) -> None:
    """Test 8: Verify temporary audio files are strictly cleaned up after transcription."""
    wav_bytes = create_sample_wav_bytes(duration_sec=1.0)

    # Track temp directory contents before and after
    temp_dir = Path(os.getenv("TMPDIR", "/tmp"))
    files_before = set(temp_dir.glob("*.wav"))

    result = stt_service.transcribe_audio_bytes(wav_bytes, filename="cleanup_test.wav")

    files_after = set(temp_dir.glob("*.wav"))

    # No leftover wav files created by this run should remain
    new_leftovers = files_after - files_before
    assert len(new_leftovers) == 0, f"Temporary file leak detected: {new_leftovers}"


@pytest.mark.asyncio
async def test_api_voice_transcribe_success(async_client: AsyncClient) -> None:
    """Test 9 & 1: API endpoint POST /api/v1/voice/transcribe returns correct response schema."""
    wav_bytes = create_sample_wav_bytes(duration_sec=1.2)
    files = {"file": ("test_voice.wav", wav_bytes, "audio/wav")}

    res = await async_client.post("/api/v1/voice/transcribe", files=files)
    assert res.status_code == 200
    data = res.json()

    assert "text" in data
    assert "language" in data
    assert "duration" in data
    assert data["duration"] > 0


@pytest.mark.asyncio
async def test_api_voice_transcribe_empty_file(async_client: AsyncClient) -> None:
    """Test 2 & 9: API endpoint returns 422 for empty file."""
    files = {"file": ("empty.wav", b"", "audio/wav")}
    res = await async_client.post("/api/v1/voice/transcribe", files=files)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_api_voice_transcribe_unsupported_format(async_client: AsyncClient) -> None:
    """Test 4 & 9: API endpoint returns 400 for unsupported format."""
    files = {"file": ("notes.txt", b"plain text payload", "text/plain")}
    res = await async_client.post("/api/v1/voice/transcribe", files=files)
    assert res.status_code == 400
    assert "unsupported" in res.json()["detail"].lower()
