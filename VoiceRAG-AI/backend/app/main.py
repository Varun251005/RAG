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

    yield  # application runs here

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


def _register_middleware(app: FastAPI, allowed_origins: list[str]) -> None:
    """Attach all middleware to the app instance."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Module-level app instance consumed by uvicorn.
app = create_app()
