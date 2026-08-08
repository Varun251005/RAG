from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Startup: configure logging, connect to external services.
    Shutdown: cleanly close connections and flush logs.
    """
    setup_logging()
    settings = get_settings()
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version} "
        f"[{settings.app_env}]"
    )

    # ── Connect vector store ───────────────────────────────────────────────────
    from app.api.deps import get_vector_store_service

    vector_store = get_vector_store_service()
    try:
        await vector_store.connect()
    except Exception as exc:  # noqa: BLE001
        # Log but don't crash — ChromaDB may start after the backend in Docker.
        logger.warning(f"ChromaDB not reachable at startup | {exc}")

    yield  # application runs here

    await vector_store.close()
    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """
    Application factory.

    Returns a fully configured FastAPI instance with:
    - CORS middleware
    - Structured exception handlers
    - Versioned API router
    - Docs enabled only in non-production
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Voice-enabled Retrieval-Augmented Generation API",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    _register_middleware(app, settings.allowed_origins)
    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


def _register_middleware(app: FastAPI, allowed_origins: list[str] | str) -> None:
    """Attach all middleware to the app instance."""
    origins = (
        [o.strip() for o in allowed_origins.split(",") if o.strip()]
        if isinstance(allowed_origins, str)
        else allowed_origins
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Module-level app instance consumed by uvicorn.
app = create_app()
