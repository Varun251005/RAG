"""
Speech-to-Text (STT) service using Faster-Whisper on CPU.
Transcribes audio files (WAV, MP3, M4A, WebM, OGG) with automatic language detection
and guaranteed temporary file cleanup.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger
from faster_whisper import WhisperModel

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac", ".aac", ".opus"}
SUPPORTED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "audio/webm",
    "audio/ogg",
    "audio/aac",
    "audio/flac",
    "audio/opus",
}


class STTServiceError(Exception):
    """Base exception for STT Service errors."""


class InvalidAudioError(STTServiceError):
    """Raised when uploaded audio is empty or invalid format."""


class STTService:
    """Dedicated Speech-to-Text service backed by Faster-Whisper CPU execution."""

    def __init__(
        self,
        model_size: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        """Lazy load and cache the Faster-Whisper model."""
        if self._model is None:
            logger.info(
                f"Loading Faster-Whisper model '{self.model_size}' (device={self.device}, compute_type={self.compute_type})..."
            )
            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as err:
                logger.error(f"Failed to load Faster-Whisper model: {err}")
                raise STTServiceError(f"Model initialization failed: {err}") from err
        return self._model

    def validate_audio(self, filename: str, content: bytes | None = None) -> None:
        """Validate audio extension and content size."""
        ext = Path(filename).suffix.lower()
        if ext and ext not in SUPPORTED_AUDIO_EXTENSIONS:
            raise InvalidAudioError(
                f"Unsupported audio format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            )

        if content is not None and len(content) == 0:
            raise InvalidAudioError("Uploaded audio content is empty (0 bytes).")

    def transcribe_file(self, file_path: Path | str) -> dict[str, Any]:
        """Transcribe an audio file from local disk."""
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            raise InvalidAudioError(f"Audio file '{path}' is missing or empty.")

        model = self._get_model()

        try:
            segments, info = model.transcribe(
                str(path),
                beam_size=5,
                vad_filter=True,
            )
            text_parts = [segment.text for segment in segments]
            full_text = " ".join(text_parts).strip()

            return {
                "text": full_text,
                "language": info.language,
                "duration": round(float(info.duration), 2),
            }
        except Exception as err:
            logger.error(f"Faster-Whisper transcription failed for {path}: {err}")
            raise STTServiceError(f"Transcription failed: {err}") from err

    def transcribe_audio_bytes(
        self,
        content: bytes,
        filename: str = "audio.wav",
    ) -> dict[str, Any]:
        """
        Transcribe raw audio bytes with guaranteed temporary file cleanup.
        """
        self.validate_audio(filename, content)

        ext = Path(filename).suffix.lower() or ".wav"

        temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        temp_path = Path(temp_file.name)

        try:
            temp_file.write(content)
            temp_file.flush()
            temp_file.close()

            result = self.transcribe_file(temp_path)
            return result
        finally:
            if temp_path.exists():
                try:
                    os.unlink(temp_path)
                except OSError as e:
                    logger.warning(f"Failed to remove temp audio file {temp_path}: {e}")
