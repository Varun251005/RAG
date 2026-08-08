"""Pydantic models for speech-to-text audio transcription."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TranscriptionResponse(BaseModel):
    """
    Successful audio transcription result returned by POST /api/v1/audio/transcribe.
    """

    text: str = Field(description="The transcribed natural-language text.")
    language: str = Field(default="en", description="Detected or specified language code.")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Audio duration in seconds.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence score.")

    model_config = ConfigDict(frozen=True)


class TranscriptionError(BaseModel):
    """Error payload returned when audio transcription fails."""

    detail: str = Field(description="Error message detailing why transcription failed.")

    model_config = ConfigDict(frozen=True)
