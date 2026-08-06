from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration loaded from environment variables.

    All fields map directly to .env keys (case-insensitive).
    Sensitive values (API keys, DB credentials) must never have defaults.
    """

    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "VoiceRAG AI"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False

    # ── API ───────────────────────────────────────────────────────────────────
    api_v1_prefix: str = "/api/v1"

    # ── Uploads ───────────────────────────────────────────────────────────────
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 25

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://voicerag:voicerag@localhost:5432/voicerag"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "voicerag"

    # ── Edge-TTS ──────────────────────────────────────────────────────────────
    edge_tts_voice: str = "en-US-AriaNeural"

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        allowed = {"development", "staging", "production"}
        if value not in allowed:
            msg = f"app_env must be one of {allowed}, got '{value}'"
            raise ValueError(msg)
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
