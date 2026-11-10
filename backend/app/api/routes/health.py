"""Liveness and readiness endpoints.

Mounted at the root, not under /api/v1, so probes do not depend on API versioning.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app import __version__
from app.api.schemas.health import LivenessResponse, ReadinessResponse
from app.dependencies import AppResources, get_resources
from app.services.system_service import build_readiness

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LivenessResponse, summary="Liveness probe")
async def liveness(
    resources: AppResources = Depends(get_resources),
) -> LivenessResponse:
    """Answer as long as the process is accepting requests."""
    return LivenessResponse(app=resources.settings.app_name, version=__version__)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
    summary="Readiness probe",
)
async def readiness(
    resources: AppResources = Depends(get_resources),
) -> JSONResponse:
    """Probe PostgreSQL, Redis and both model servers.

    503 only when a critical dependency (PostgreSQL or Redis) is unavailable;
    a missing model server returns 200 with status ``degraded``.
    """
    report = await build_readiness(resources)
    status_code = 503 if report.status == "unavailable" else 200
    return JSONResponse(status_code=status_code, content=report.model_dump())
