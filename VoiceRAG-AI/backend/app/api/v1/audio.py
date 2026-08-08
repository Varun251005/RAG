"""Audio API router — handles speech-to-text audio upload and transcription."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from loguru import logger

from app.api.deps import get_transcription_service
from app.core.exceptions import UnprocessableError
from app.models.transcription import TranscriptionResponse
from app.services.transcription_service import TranscriptionService

router = APIRouter()


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    summary="Transcribe spoken audio to text",
    description=(
        "Receives a microphone audio recording (webm, wav, ogg, mp3) "
        "and transcribes the speech into text using Whisper / Gemini STT."
    ),
    tags=["Audio"],
)
async def transcribe_audio_endpoint(
    file: UploadFile = File(description="Recorded audio binary file."),
    service: TranscriptionService = Depends(get_transcription_service),
) -> TranscriptionResponse:
    if not file or not file.filename:
        raise UnprocessableError("No audio file provided.")

    logger.info(f"Audio upload received | filename={file.filename} | content_type={file.content_type}")

    audio_bytes = await file.read()
    mime_type = file.content_type or "audio/webm"

    return await service.transcribe_audio(
        audio_bytes=audio_bytes,
        mime_type=mime_type,
        filename=file.filename,
    )
