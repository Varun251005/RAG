"""Pydantic models for Text-to-Speech (TTS) audio generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VoiceSynthesizeRequest(BaseModel):
    """
    Request payload for POST /api/v1/voice/synthesize.
    """

    text: str = Field(description="Natural language text to convert into speech.")
    voice: str | None = Field(default=None, description="Optional Edge-TTS voice identifier.")

    model_config = ConfigDict(frozen=True)


class TTSQuery(BaseModel):
    """
    Request body for POST /api/v1/tts/stream.
    """

    text: str = Field(min_length=1, max_length=5000, description="Text to synthesize.")
    voice: str = Field(default="en-US-AvaNeural", description="Edge-TTS voice name.")
    rate: str = Field(default="+0%", description="Speech rate adjustment string.")

    model_config = ConfigDict(frozen=True)


class TTSVoice(BaseModel):
    """Voice metadata object."""

    name: str = Field(description="Full voice name.")
    short_name: str = Field(description="Short identifier, e.g. en-US-AvaNeural.")
    gender: str = Field(description="Gender (Female/Male).")
    locale: str = Field(description="Language locale code, e.g. en-US.")

    model_config = ConfigDict(frozen=True)


class TTSVoicesResponse(BaseModel):
    """List of available TTS voices."""

    voices: list[TTSVoice]
    total: int = Field(ge=0)

    model_config = ConfigDict(frozen=True)
