from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import VectorStoreService

# Module-level singleton — one service instance for the process lifetime.
# Will be replaced with proper async DI factories when DB is introduced.
_document_service: DocumentService | None = None


def get_app_settings() -> Settings:
    """Provide the application settings to route handlers via Depends()."""
    return get_settings()


def get_document_service() -> DocumentService:
    """
    Return the singleton DocumentService instance.

    Reads upload configuration from Settings so no values are hardcoded.
    """
    global _document_service  # noqa: PLW0603

    if _document_service is None:
        settings = get_settings()
        _document_service = DocumentService(
            upload_dir=Path(settings.upload_dir),
            max_upload_bytes=settings.max_upload_size_mb * 1024 * 1024,
        )

    return _document_service


# ---------------------------------------------------------------------------
# EmbeddingService singleton
# ---------------------------------------------------------------------------

_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """
    Return the singleton EmbeddingService instance.

    The service is constructed lazily on first call so the API key is only
    read once Settings is fully loaded.  Inject a mock via
    ``deps._embedding_service = ...`` in tests.
    """
    global _embedding_service  # noqa: PLW0603

    if _embedding_service is None:
        _embedding_service = EmbeddingService()

    return _embedding_service


# ---------------------------------------------------------------------------
# VectorStoreService singleton
# ---------------------------------------------------------------------------

_vector_store_service: VectorStoreService | None = None


def get_vector_store_service() -> VectorStoreService:
    """
    Return the singleton VectorStoreService instance.

    The ChromaDB HTTP client is initialised lazily on first access.
    In tests, inject a mock via ``deps._vector_store_service = ...``.
    """
    global _vector_store_service  # noqa: PLW0603

    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()

    return _vector_store_service


# ---------------------------------------------------------------------------
# RAGService singleton
# ---------------------------------------------------------------------------

_rag_service = None  # type: ignore[assignment]


def get_rag_service():  # type: ignore[return]
    """
    Return the singleton RAGService instance.

    Composed from the EmbeddingService and VectorStoreService singletons.
    Inject a mock via ``deps._rag_service = ...`` in tests.
    """
    # Import here to avoid circular imports at module load time.
    from app.services.rag_service import RAGService  # noqa: PLC0415

    global _rag_service  # noqa: PLW0603

    if _rag_service is None:
        _rag_service = RAGService(
            embedding_service=get_embedding_service(),
            vector_store_service=get_vector_store_service(),
        )

    return _rag_service


# ---------------------------------------------------------------------------
# TranscriptionService singleton
# ---------------------------------------------------------------------------

_transcription_service = None  # type: ignore[assignment]


def get_transcription_service():  # type: ignore[return]
    """
    Return the singleton TranscriptionService instance.

    Inject a mock via ``deps._transcription_service = ...`` in tests.
    """
    from app.services.transcription_service import TranscriptionService  # noqa: PLC0415

    global _transcription_service  # noqa: PLW0603

    if _transcription_service is None:
        _transcription_service = TranscriptionService()

    return _transcription_service


# ---------------------------------------------------------------------------
# TTSService singleton
# ---------------------------------------------------------------------------

_tts_service = None  # type: ignore[assignment]


def get_tts_service():  # type: ignore[return]
    """
    Return the singleton TTSService instance.

    Inject a mock via ``deps._tts_service = ...`` in tests.
    """
    from app.services.tts_service import TTSService  # noqa: PLC0415

    global _tts_service  # noqa: PLW0603

    if _tts_service is None:
        _tts_service = TTSService()

    return _tts_service



