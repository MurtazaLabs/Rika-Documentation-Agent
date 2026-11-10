"""Dependency health probes.

Each probe is time-boxed and never raises: readiness must answer quickly and
report *which* dependency is down instead of failing the request.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.api.schemas.health import DependencyCheck, ReadinessResponse
from app.core.constants import CRITICAL_DEPENDENCIES
from app.dependencies import AppResources
from app.llm.llama_client import ModelServerClient

logger = logging.getLogger(__name__)


def _is_critical(name: str) -> bool:
    return name in CRITICAL_DEPENDENCIES


def _error_detail(exc: BaseException) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return "timed out"
    text_detail = str(exc).strip()
    return f"{exc.__class__.__name__}: {text_detail}" if text_detail else exc.__class__.__name__


async def check_postgres(engine: AsyncEngine, *, timeout: float) -> DependencyCheck:
    async def probe() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(probe(), timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - every failure is reported, not raised
        logger.debug("postgres probe failed", exc_info=exc)
        return DependencyCheck(
            name="postgres", status="error", critical=_is_critical("postgres"),
            detail=_error_detail(exc),
        )
    return DependencyCheck(name="postgres", status="ok", critical=_is_critical("postgres"))


async def check_redis(client: Redis, *, timeout: float) -> DependencyCheck:
    try:
        await asyncio.wait_for(client.ping(), timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.debug("redis probe failed", exc_info=exc)
        return DependencyCheck(
            name="redis", status="error", critical=_is_critical("redis"),
            detail=_error_detail(exc),
        )
    return DependencyCheck(name="redis", status="ok", critical=_is_critical("redis"))


async def check_model(
    client: ModelServerClient, *, name: str, timeout: float
) -> DependencyCheck:
    critical = _is_critical(name)
    try:
        models = await asyncio.wait_for(client.list_models(), timeout=timeout)
    except asyncio.TimeoutError:
        return DependencyCheck(
            name=name,
            status="error",
            critical=critical,
            detail=(
                f"no response from {client.base_url} within {timeout:g}s "
                "(is the model server running?)"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("%s probe failed", name, exc_info=exc)
        return DependencyCheck(
            name=name, status="error", critical=critical, detail=_error_detail(exc)
        )

    if not models:
        detail = "server reachable but reports no models"
    elif client.model_name in models:
        detail = f"model '{client.model_name}' available"
    else:
        detail = f"model '{client.model_name}' not listed (available: {', '.join(models)})"
    return DependencyCheck(name=name, status="ok", critical=critical, detail=detail)


def evaluate_status(checks: Sequence[DependencyCheck]) -> str:
    """Collapse individual probes into one overall readiness status."""
    if any(check.critical and check.status != "ok" for check in checks):
        return "unavailable"
    if any(check.status != "ok" for check in checks):
        return "degraded"
    return "ready"


async def build_readiness(resources: AppResources) -> ReadinessResponse:
    settings = resources.settings
    checks = await asyncio.gather(
        check_postgres(resources.engine, timeout=settings.readiness_timeout),
        check_redis(resources.redis, timeout=settings.readiness_timeout),
        check_model(
            resources.chat_client,
            name="chat_model",
            timeout=settings.readiness_timeout,
        ),
        check_model(
            resources.embedding_client,
            name="embedding_model",
            timeout=settings.readiness_timeout,
        ),
    )

    status = evaluate_status(checks)
    if status != "ready":
        logger.warning(
            "readiness %s: %s",
            status,
            ", ".join(f"{c.name}={c.status}" for c in checks if c.status != "ok"),
        )

    return ReadinessResponse(
        status=status,  # type: ignore[arg-type]
        app=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        checks=list(checks),
    )
