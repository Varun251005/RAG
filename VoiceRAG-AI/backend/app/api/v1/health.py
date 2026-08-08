"""Health check route — GET /api/v1/health."""

from fastapi import APIRouter
from loguru import logger

from app.core.config import Settings, get_settings
from app.models.health import HealthResponse, HealthStatus

router = APIRouter()


async def _check_dependencies() -> dict[str, HealthStatus]:
    """
    Probe each external dependency.

    ChromaDB: attempts a real heartbeat via the singleton VectorStoreService.
    PostgreSQL: placeholder until the DB layer is added.
    """
    results: dict[str, HealthStatus] = {}

    # ── PostgreSQL ─────────────────────────────────────────────────────────
    # Placeholder: will perform an actual async ping when the DB layer lands.
    results["postgres"] = HealthStatus(status="not_configured", detail="Phase 02")

    # ── ChromaDB ───────────────────────────────────────────────────────────
    try:
        from app.api.deps import get_vector_store_service

        svc = get_vector_store_service()
        client = await svc._get_client()  # noqa: SLF001
        # list_collections is the lightest call that confirms the server is up.
        await client.list_collections()
        results["chromadb"] = HealthStatus(status="ok")
    except Exception as exc:  # noqa: BLE001
        results["chromadb"] = HealthStatus(
            status="unreachable",
            detail=str(exc)[:120],
        )

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
