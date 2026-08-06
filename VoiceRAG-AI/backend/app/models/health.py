from pydantic import BaseModel


class HealthStatus(BaseModel):
    """Represents the health state of a single dependency."""

    status: str  # "ok" | "degraded" | "unreachable"
    detail: str = ""


class HealthResponse(BaseModel):
    """Top-level health check response returned by GET /api/v1/health."""

    status: str  # "ok" | "degraded"
    env: str
    version: str
    dependencies: dict[str, HealthStatus] = {}
