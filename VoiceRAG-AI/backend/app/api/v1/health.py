from fastapi import APIRouter
from loguru import logger

from app.core.config import Settings, get_settings
from app.models.health import HealthResponse, HealthStatus

router = APIRouter()


async def _check_dependencies() -> dict[str, HealthStatus]:
    """
    Probe each external dependency.

    Returns a dict keyed by dependency name.
    Designed to be extended as DB, ChromaDB, and Gemini are integrated.
    """
    results: dict[str, HealthStatus] = {}

    # ── PostgreSQL ─────────────────────────────────────────────────────────
    # Placeholder: will perform an actual async ping in Phase 02.
    results["postgres"] = HealthStatus(status="not_configured", detail="Phase 02")

    # ── ChromaDB ───────────────────────────────────────────────────────────
    results["chromadb"] = HealthStatus(status="not_configured", detail="Phase 03")

    return results


def _overall_status(deps: dict[str, HealthStatus]) -> str:
    """Derive top-level status from dependency statuses."""
    degraded = any(d.status not in {"ok", "not_configured"} for d in deps.values())
    return "degraded" if degraded else "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service health and the status of each dependency.",
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    settings: Settings = get_settings()

    logger.debug("Health check requested")

    deps = await _check_dependencies()
    status = _overall_status(deps)

    logger.info(f"Health check completed | status={status}")

    return HealthResponse(
        status=status,
        env=settings.app_env,
        version=settings.app_version,
        dependencies=deps,
    )
