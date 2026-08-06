from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.document_service import DocumentService

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
