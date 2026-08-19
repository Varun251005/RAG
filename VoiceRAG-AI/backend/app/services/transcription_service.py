"""
Transcription Service — Speech-to-Text audio transcription.

Transcribes audio recorded via MediaRecorder (webm, wav, ogg, mp3)
using Whisper / Gemini audio transcription.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from loguru import logger

from app.core.config import get_settings
from app.core.exceptions import ServiceError, UnprocessableError
from app.models.transcription import TranscriptionResponse

ALLOWED_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/mp3",
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
    "audio/aac",
}


class TranscriptionService:
    """
    Speech-to-Text service supporting Whisper engine with Gemini audio API fallback.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        cfg = get_settings()
        self._api_key = api_key or cfg.gemini_api_key
        self._model = model or cfg.gemini_model
        self._whisper_model = None

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
        filename: str | None = None,
    ) -> TranscriptionResponse:
        """
        Transcribe audio bytes into text.

        Parameters
        ----------
        audio_bytes :
            Raw audio binary data.
        mime_type :
            MIME type of the audio recording (e.g. "audio/webm").
        filename :
            Optional original filename.

        Returns
        -------
        TranscriptionResponse
            Transcribed text, language code, and metadata.
        """
        if not audio_bytes or len(audio_bytes) < 100:
            raise UnprocessableError("Audio data is empty or too short.")

        # Normalize mime type (remove codecs params if present, e.g. "audio/webm;codecs=opus")
        clean_mime = mime_type.split(";")[0].strip().lower()
        if clean_mime not in ALLOWED_MIME_TYPES and not clean_mime.startswith("audio/"):
            logger.warning(f"Unrecognized audio MIME type: {mime_type}, proceeding as audio/webm")
            clean_mime = "audio/webm"

        logger.info(f"Transcribing audio | bytes={len(audio_bytes)} | mime={clean_mime}")

        # Strategy 1: Try Whisper if faster_whisper or whisper package is installed
        try:
            text = await self._transcribe_with_whisper(audio_bytes, clean_mime)
            if text and text.strip():
                return TranscriptionResponse(
                    text=text.strip(),
                    language="en",
                    duration_seconds=0.0,
                    confidence=0.98,
                )
        except Exception as exc:
            logger.debug(f"Local Whisper transcription skipped/failed: {exc!r}. Using Gemini Audio engine...")

        # Strategy 2: Gemini Multimodal Audio Transcription
        try:
            text = await self._transcribe_with_gemini(audio_bytes, clean_mime)
            return TranscriptionResponse(
                text=text.strip(),
                language="en",
                duration_seconds=0.0,
                confidence=0.95,
            )
        except Exception as exc:
            logger.error(f"Audio transcription failed | {exc!r}")
            raise ServiceError(f"Speech-to-Text transcription failed: {exc}") from exc

    async def _transcribe_with_whisper(self, audio_bytes: bytes, mime_type: str) -> str:
        """Attempt transcription using faster_whisper if installed."""
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError:
            try:
                import whisper  # type: ignore[import-not-found]
                with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                try:
                    wmodel = whisper.load_model("tiny")
                    result = wmodel.transcribe(tmp_path)
                    return str(result.get("text", ""))
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
            except ImportError:
                raise RuntimeError("Whisper package not available locally") from None

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            if self._whisper_model is None:
                self._whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _info = self._whisper_model.transcribe(tmp_path, beam_size=5)
            text = " ".join([seg.text for seg in segments])
            return text
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _transcribe_with_gemini(self, audio_bytes: bytes, mime_type: str) -> str:
        """Transcribe audio using Google GenAI API."""
        if not self._api_key:
            raise ServiceError("GEMINI_API_KEY is not configured for transcription.")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._api_key)
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

        prompt = (
            "You are a high-accuracy Speech-to-Text transcriber. "
            "Listen to the attached audio recording and transcribe every word accurately. "
            "Do not add any explanations, introductory text, or commentary. "
            "Return ONLY the plain text transcription of the spoken words."
        )

        response = client.models.generate_content(
            model=self._model,
            contents=[prompt, audio_part],
        )

        text = response.text or ""
        return text.strip()
