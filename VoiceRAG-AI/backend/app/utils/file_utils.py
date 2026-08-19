import hashlib
import re
from pathlib import Path

# Only PDF is accepted.
_ALLOWED_MIME_TYPES: frozenset[str] = frozenset({"application/pdf"})
_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

# PDF files always start with these bytes.
_PDF_MAGIC: bytes = b"%PDF"


class FileValidationError(ValueError):
    """Raised when an uploaded file fails security or format validation."""


def validate_pdf(filename: str, content: bytes, content_type: str, max_bytes: int) -> None:
    """
    Run all validation checks on an uploaded file.

    Order matters: cheap checks (extension, MIME) run before reading content.
    """
    _check_extension(filename)
    _check_mime(content_type)
    _check_size(content, max_bytes)
    _check_magic(content)


def compute_sha256(content: bytes) -> str:
    """Return the hex SHA-256 digest of file content (used for dedup)."""
    return hashlib.sha256(content).hexdigest()


def sanitize_filename(filename: str) -> str:
    """
    Return a filesystem-safe stem from the original filename.

    Replaces all non-alphanumeric characters (except hyphens) with underscores.
    Caps at 100 characters to prevent path length issues.
    """
    stem = Path(filename).stem
    safe = re.sub(r"[^\w\-]", "_", stem).strip("_")
    return (safe or "document")[:100]


def _check_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Extension '{ext}' is not allowed. Only .pdf files are accepted."
        )


def _check_mime(content_type: str) -> None:
    # Strip parameters such as '; charset=utf-8'
    base = content_type.split(";")[0].strip().lower()
    if base not in _ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"MIME type '{base}' is not accepted. Expected 'application/pdf'."
        )


def _check_size(content: bytes, max_bytes: int) -> None:
    if len(content) > max_bytes:
        mb = len(content) / (1024 * 1024)
        limit_mb = max_bytes / (1024 * 1024)
        raise FileValidationError(
            f"File size {mb:.1f} MB exceeds the {limit_mb:.0f} MB limit."
        )


def _check_magic(content: bytes) -> None:
    if not content.startswith(_PDF_MAGIC):
        raise FileValidationError(
            "File is not a valid PDF (failed magic-bytes check)."
        )
