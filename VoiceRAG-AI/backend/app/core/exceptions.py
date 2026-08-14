from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger


# ---------------------------------------------------------------------------
# Domain exception hierarchy
# ---------------------------------------------------------------------------


class AppException(Exception):
    """Base exception for all application-level errors."""

    def __init__(self, status_code: int, message: str, detail: str = "") -> None:
        self.status_code = status_code
        self.message = message
        self.detail = detail
        super().__init__(detail or message)

    def __str__(self) -> str:
        return self.detail or self.message



class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            status_code=404,
            message=f"{resource} not found",
            detail=f"{resource} with identifier '{identifier}' does not exist.",
        )


class ConflictError(AppException):
    """Raised when an operation violates a uniqueness constraint."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=409, message="Conflict", detail=detail)


class ServiceError(AppException):
    """Raised when an internal service or external dependency fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=500, message="Service error", detail=detail)


class UnprocessableError(AppException):
    """Raised when input is structurally valid but semantically wrong."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=422, message="Unprocessable content", detail=detail
        )


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


async def _app_exception_handler(
    request: Request, exc: AppException
) -> JSONResponse:
    logger.warning(
        f"AppException | {exc.status_code} {exc.message} | "
        f"path={request.url.path} | detail={exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail},
    )


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        f"Unhandled exception | path={request.url.path} | error={exc!r}"
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again.",
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""
    app.add_exception_handler(AppException, _app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_exception_handler)
