"""
Text-to-Speech (TTS) service backed by Microsoft Edge-TTS library.
Generates MP3 audio streams/bytes on CPU with configurable neural voices.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import get_settings


_AVAILABLE_VOICES = [
    {"name": "Microsoft Ava Online (Natural) - English (United States)", "short_name": "en-US-AvaNeural", "gender": "Female", "locale": "en-US"},
    {"name": "Microsoft Emma Online (Natural) - English (United States)", "short_name": "en-US-EmmaNeural", "gender": "Female", "locale": "en-US"},
    {"name": "Microsoft Andrew Online (Natural) - English (United States)", "short_name": "en-US-AndrewNeural", "gender": "Male", "locale": "en-US"},
    {"name": "Microsoft Brian Online (Natural) - English (United States)", "short_name": "en-US-BrianNeural", "gender": "Male", "locale": "en-US"},
    {"name": "Microsoft Guy Online (Natural) - English (United States)", "short_name": "en-US-GuyNeural", "gender": "Male", "locale": "en-US"},
    {"name": "Microsoft Jenny Online (Natural) - English (United States)", "short_name": "en-US-JennyNeural", "gender": "Female", "locale": "en-US"},
    {"name": "Microsoft Aria Online (Natural) - English (United States)", "short_name": "en-US-AriaNeural", "gender": "Female", "locale": "en-US"},
    {"name": "Microsoft Ryan Online (Natural) - English (United Kingdom)", "short_name": "en-GB-RyanNeural", "gender": "Male", "locale": "en-GB"},
    {"name": "Microsoft Sonia Online (Natural) - English (United Kingdom)", "short_name": "en-GB-SoniaNeural", "gender": "Female", "locale": "en-GB"},
]


class TTSServiceError(Exception):
    """Base exception for TTS service errors."""


class InvalidTTSTextError(TTSServiceError):
    """Raised when input text is empty or exceeds configured maximum length."""


class TTSService:
    """
    Dedicated Text-to-Speech service powered by Edge-TTS (CPU execution).
    """

    def __init__(
        self,
        default_voice: str | None = None,
        max_text_length: int | None = None,
    ) -> None:
        cfg = get_settings()
        self.default_voice = default_voice or getattr(cfg, "edge_tts_voice", "en-US-AvaNeural")
        self.max_text_length = max_text_length or getattr(cfg, "tts_max_text_length", 4096)

    def _clean_text_for_speech(self, text: str) -> str:
        """Strip markdown elements, code blocks, URLs, and extra whitespace for natural speech."""
        if not text:
            return ""

        # Remove code blocks ```...```
        cleaned = re.sub(r"```[\s\S]*?```", " [code block omitted] ", text)
        # Remove inline code `...`
        cleaned = re.sub(r"`[^`]+`", "", cleaned)
        # Remove markdown link syntax [label](url) -> label
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        # Remove markdown headers #, ##, etc.
        cleaned = re.sub(r"#+\s*", "", cleaned)
        # Remove bold/italic formatting *, **
        cleaned = re.sub(r"\*{1,3}([^\*]+)\*{1,3}", r"\1", cleaned)
        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def validate_text(self, text: str) -> str:
        """Validate text length and non-emptiness."""
        cleaned = self._clean_text_for_speech(text)
        if not cleaned:
            raise InvalidTTSTextError("Text content is empty after cleaning.")

        if len(cleaned) > self.max_text_length:
            raise InvalidTTSTextError(
                f"Text length ({len(cleaned)} chars) exceeds maximum allowed limit of {self.max_text_length} characters."
            )

        return cleaned

    async def synthesize_speech(self, text: str, voice: str | None = None) -> bytes:
        """
        Synthesize text into MP3 audio bytes using Edge-TTS asynchronously.
        Guarantees temporary file cleanup when disk buffer is used.
        """
        cleaned_text = self.validate_text(text)
        chosen_voice = voice.strip() if voice and voice.strip() else self.default_voice

        logger.info(f"Synthesizing TTS | voice={chosen_voice} | text_len={len(cleaned_text)}")

        import edge_tts

        try:
            communicate = edge_tts.Communicate(text=cleaned_text, voice=chosen_voice)
            audio_buffer = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            audio_bytes = audio_buffer.getvalue()

            if len(audio_bytes) == 0:
                raise TTSServiceError(f"Edge-TTS produced 0 bytes for voice '{chosen_voice}'.")

            return audio_bytes

        except Exception as err:
            logger.warning(f"Edge-TTS synthesis failed with voice '{chosen_voice}': {err}")

            # If a custom invalid/unavailable voice was specified, fall back to default voice
            if chosen_voice != self.default_voice:
                logger.info(f"Falling back to default voice '{self.default_voice}'")
                try:
                    communicate_fallback = edge_tts.Communicate(text=cleaned_text, voice=self.default_voice)
                    fallback_buffer = io.BytesIO()
                    async for chunk in communicate_fallback.stream():
                        if chunk["type"] == "audio":
                            fallback_buffer.write(chunk["data"])
                    fallback_bytes = fallback_buffer.getvalue()
                    if len(fallback_bytes) > 0:
                        return fallback_bytes
                except Exception as fallback_err:
                    logger.error(f"Fallback TTS synthesis also failed: {fallback_err}")

            raise TTSServiceError(f"Speech synthesis failed: {err}") from err

    async def synthesize_to_temp_file(self, text: str, voice: str | None = None) -> Path:
        """
        Synthesize audio into a temporary MP3 file on disk for file cleanup testing.
        Caller is responsible for unlinking path, or using try...finally block.
        """
        audio_bytes = await self.synthesize_speech(text, voice)
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_path = Path(temp_file.name)
        try:
            temp_file.write(audio_bytes)
            temp_file.flush()
            temp_file.close()
            return temp_path
        except Exception:
            if temp_path.exists():
                os.unlink(temp_path)
            raise

    def list_voices(self) -> list[dict[str, str]]:
        """
        Return a curated list of available Edge-TTS neural voice descriptors.
        """
        return _AVAILABLE_VOICES

    async def stream_speech(
        self,
        text: str,
        voice: str | None = None,
        rate: str = "+0%",
    ) -> AsyncGenerator[bytes, None]:
        """
        Async generator that streams MP3 audio chunks from Edge-TTS for use
        with FastAPI StreamingResponse.
        """
        cleaned_text = self.validate_text(text)
        chosen_voice = voice.strip() if voice and voice.strip() else self.default_voice

        logger.info(f"Streaming TTS | voice={chosen_voice} | rate={rate} | text_len={len(cleaned_text)}")

        import edge_tts

        communicate = edge_tts.Communicate(text=cleaned_text, voice=chosen_voice, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
