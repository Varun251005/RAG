"""TTS API router — text-to-speech streaming audio generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.deps import get_tts_service
from app.models.tts import TTSQuery, TTSVoicesResponse
from app.services.tts_service import TTSService

router = APIRouter()


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="Synthesize and stream text-to-speech audio",
    description="Synthesizes input text into spoken audio MP3 stream using Edge-TTS.",
    tags=["TTS"],
)
async def tts_stream_endpoint(
    query: TTSQuery,
    service: TTSService = Depends(get_tts_service),
) -> StreamingResponse:
    logger.info(f"TTS audio requested | text_len={len(query.text)} | voice={query.voice} | rate={query.rate}")

    generator = service.stream_speech(
        text=query.text,
        voice=query.voice,
        rate=query.rate,
    )

    return StreamingResponse(
        generator,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": "inline; filename=speech.mp3",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/voices",
    response_model=TTSVoicesResponse,
    summary="List available Edge-TTS voices",
    description="Returns list of high-quality Microsoft Edge neural voices.",
    tags=["TTS"],
)
async def get_voices_endpoint(
    service: TTSService = Depends(get_tts_service),
) -> TTSVoicesResponse:
    from app.models.tts import TTSVoice as TVoice
    raw = service.list_voices()
    voices = [
        TVoice(
            name=v["name"],
            short_name=v["short_name"],
            gender=v["gender"],
            locale=v["locale"],
        )
        for v in raw
    ]
    return TTSVoicesResponse(voices=voices, total=len(voices))
