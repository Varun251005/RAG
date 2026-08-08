"""Pydantic models for speech-to-text audio transcription."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VoiceTranscribeResponse(BaseModel):
    """
    Response schema for POST /api/v1/voice/transcribe.
    """

    text: str = Field(description="Transcribed natural-language text from audio.")
    language: str = Field(description="Detected language code (e.g. 'en', 'es').")
    duration: float = Field(ge=0.0, description="Audio duration in seconds.")

    model_config = ConfigDict(frozen=True)


class TranscriptionResponse(BaseModel):
    """
    Legacy audio transcription result returned by POST /api/v1/audio/transcribe.
    """

    text: str = Field(description="The transcribed natural-language text.")
    language: str = Field(default="en", description="Detected or specified language code.")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Audio duration in seconds.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence score.")

    model_config = ConfigDict(frozen=True)


class TranscriptionErrorResponse(BaseModel):
    """Error response schema."""

    detail: str = Field(description="Description of the transcription or validation error.")

    model_config = ConfigDict(frozen=True)
