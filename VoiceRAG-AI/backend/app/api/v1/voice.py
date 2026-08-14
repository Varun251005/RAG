"""FastAPI endpoints for Voice-to-Text (STT) and Text-to-Speech (TTS)."""

from __future__ import annotations

from typing import Annotated
from loguru import logger
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.api.deps import get_stt_service, get_tts_service
from app.models.transcription import VoiceTranscribeResponse
from app.models.tts import VoiceSynthesizeRequest
from app.services.stt_service import InvalidAudioError, STTService, STTServiceError
from app.services.tts_service import InvalidTTSTextError, TTSService, TTSServiceError

router = APIRouter()


@router.post(
    "/transcribe",
    response_model=VoiceTranscribeResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe uploaded audio file using local Faster-Whisper (CPU)",
    description="Accepts WAV, MP3, M4A, WebM, or OGG audio files and returns transcribed text, language, and duration.",
)
async def transcribe_voice_audio(
    file: Annotated[UploadFile | None, File(description="Uploaded audio file")] = None,
    audio: Annotated[UploadFile | None, File(description="Alternative field name for audio file")] = None,
    stt_service: STTService = Depends(get_stt_service),
) -> VoiceTranscribeResponse:
    target_file = file or audio

    if not target_file or not target_file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No audio file provided in request. Please upload an audio file.",
        )

    content = await target_file.read()

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded audio file is empty (0 bytes).",
        )

    try:
        result = stt_service.transcribe_audio_bytes(content, filename=target_file.filename)
        return VoiceTranscribeResponse(
            text=result["text"],
            language=result["language"],
            duration=result["duration"],
        )
    except InvalidAudioError as err:
        logger.warning(f"Audio validation failed for '{target_file.filename}': {err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except STTServiceError as err:
        logger.error(f"STT transcription failed for '{target_file.filename}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech-to-text transcription failed: {err}",
        ) from err
    except Exception as err:
        logger.error(f"Unexpected error transcribing '{target_file.filename}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during audio processing: {err}",
        ) from err


@router.post(
    "/synthesize",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Synthesize speech audio from text using Edge-TTS (CPU)",
    description="Converts natural language text into browser-playable MP3 audio stream using Edge-TTS.",
)
async def synthesize_voice_speech(
    payload: VoiceSynthesizeRequest,
    tts_service: TTSService = Depends(get_tts_service),
) -> Response:
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Text payload for speech synthesis cannot be empty.",
        )

    try:
        audio_bytes = await tts_service.synthesize_speech(
            text=payload.text,
            voice=payload.voice,
        )

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": 'inline; filename="speech.mp3"',
                "Content-Length": str(len(audio_bytes)),
            },
        )
    except InvalidTTSTextError as err:
        logger.warning(f"TTS text validation failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        ) from err
    except TTSServiceError as err:
        logger.error(f"TTS synthesis failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text-to-speech synthesis failed: {err}",
        ) from err
    except Exception as err:
        logger.error(f"Unexpected error during TTS synthesis: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during speech synthesis: {err}",
        ) from err
