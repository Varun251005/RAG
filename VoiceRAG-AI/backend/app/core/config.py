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

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    # ── RAG pipeline ──────────────────────────────────────────────────────────
    # Number of chunks retrieved from ChromaDB per query.
    rag_top_k: int = 5
    # Maximum tokens the LLM may produce in one answer.
    rag_max_output_tokens: int = 2048
    # Lower temperature → more factual / deterministic answers.
    rag_temperature: float = 0.2
    # Minimum similarity score to include a chunk (0–1, cosine).
    rag_score_threshold: float = 0.0

    # ── Embedding pipeline ────────────────────────────────────────────────────
    # Chunks sent per Gemini API call (max 100 for text-embedding-004).
    embedding_batch_size: int = 100
    # Concurrent API calls in flight at once.
    embedding_max_concurrent: int = 5
    # Per-call retry attempts on transient errors.
    embedding_max_retries: int = 3
    # Exponential back-off base in seconds (full-jitter applied).
    embedding_retry_base_secs: float = 1.0
    # Directory for the L2 disk embedding cache.
    embedding_cache_dir: str = ".embedding_cache"
    # Maximum entries held in the L1 in-memory LRU cache.
    embedding_cache_max_mem: int = 2048

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://voicerag:voicerag@localhost:5432/voicerag"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "voicerag"
    # Local persistent directory used when running without the Docker server.
    chroma_persist_dir: str = ".chroma"

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
