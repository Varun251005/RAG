"""
Frontend Voice Input Integration Test Suite for VoiceRAG AI.
Tests end-to-end flow from voice recording transcription to chat input and RAG querying.
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
    vector_svc = VectorStoreService(default_collection="test_voice_flow")
    vector_svc._client = chromadb.EphemeralClient()
    app.dependency_overrides[get_vector_store_service] = lambda: vector_svc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_1_voice_transcription_endpoint(async_client: AsyncClient) -> None:
    """Test 1: Voice transcription endpoint accepts recorded audio blob and returns transcribed text."""
    audio_bytes = create_sample_wav_bytes(duration_sec=1.2)
    files = {"file": ("recording.webm", audio_bytes, "audio/webm")}

    res = await async_client.post("/api/v1/voice/transcribe", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "text" in data
    assert "language" in data
    assert "duration" in data


@pytest.mark.asyncio
async def test_2_transcribed_text_sent_to_chat_with_document_filter(async_client: AsyncClient) -> None:
    """Test 2: Transcribed text is reviewed/edited and sent to /api/v1/chat preserving document_id filter."""
    pdf_bytes = create_sample_pdf_bytes("Quantum computing uses qubits to perform complex calculations.")
    upload_res = await async_client.post("/api/v1/documents/upload", files={"file": ("quantum.pdf", pdf_bytes, "application/pdf")})
    doc_id = upload_res.json()["document_id"]

    # Simulating STT output populated into chat input box
    transcribed_text = "What is quantum computing used for?"
    user_edited_text = transcribed_text + " Explain simply."

    chat_payload = {
        "question": user_edited_text,
        "document_id": doc_id,
    }
    chat_res = await async_client.post("/api/v1/chat", json=chat_payload)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "answer" in chat_data
    assert len(chat_data["sources"]) > 0
    assert chat_data["sources"][0]["document_id"] == doc_id
