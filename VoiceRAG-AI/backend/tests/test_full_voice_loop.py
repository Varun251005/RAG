"""
End-to-End Voice Loop Test Suite for VoiceRAG AI.
Verifies complete flow: Audio Recording -> Faster-Whisper STT -> ChromaDB RAG -> Qwen LLM -> Edge-TTS -> MP3 Audio.
"""

from __future__ import annotations

import io
import math
import struct
import wave
import pytest
import fitz
from httpx import ASGITransport, AsyncClient

import chromadb
from app.api.deps import get_vector_store_service
from app.main import app
from app.services.vector_store_service import VectorStoreService


def create_sample_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    num_samples = int(sample_rate * duration_sec)
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(num_samples):
            val = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            wav.writeframes(struct.pack("<h", val))
    return buf.getvalue()


def create_sample_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
async def async_client() -> AsyncClient:
    vector_svc = VectorStoreService(default_collection="test_voice_loop")
    vector_svc._client = chromadb.EphemeralClient()
    app.dependency_overrides[get_vector_store_service] = lambda: vector_svc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_full_voice_loop_stt_rag_qwen_tts(async_client: AsyncClient) -> None:
    """Test full voice loop: STT -> RAG -> Qwen -> Edge-TTS."""
    # 1. Upload reference PDF document
    pdf_bytes = create_sample_pdf_bytes("Artificial Intelligence uses machine learning algorithms to process data.")
    upload_res = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("ai_overview.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code in (200, 201)
    doc_id = upload_res.json()["document_id"]

    # 2. Transcribe voice audio (Faster-Whisper STT)
    audio_bytes = create_sample_wav_bytes(duration_sec=1.5)
    stt_res = await async_client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("mic_recording.webm", audio_bytes, "audio/webm")},
    )
    assert stt_res.status_code == 200
    stt_data = stt_res.json()
    assert "text" in stt_data

    # 3. Query RAG Chat API with document_id filter
    question = "What does artificial intelligence use?"
    chat_res = await async_client.post(
        "/api/v1/chat",
        json={"question": question, "document_id": doc_id},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    answer_text = chat_data["answer"]
    assert len(answer_text) > 0
    assert len(chat_data["sources"]) > 0

    # 4. Synthesize speech for assistant answer via Edge-TTS
    tts_res = await async_client.post(
        "/api/v1/voice/synthesize",
        json={"text": answer_text, "voice": "en-US-AvaNeural"},
    )
    assert tts_res.status_code == 200
    assert tts_res.headers["content-type"] == "audio/mpeg"
    assert len(tts_res.content) > 500  # Non-empty MP3 stream
