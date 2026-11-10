"""Health and readiness response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DependencyCheck(BaseModel):
    """Result of probing one backing service."""

    name: str
    status: Literal["ok", "error"]
    critical: bool
    detail: str | None = None


class LivenessResponse(BaseModel):
    status: Literal["alive"] = "alive"
    app: str
    version: str


class ReadinessResponse(BaseModel):
    """Overall status plus every probe.

    ``ready`` means all critical dependencies answered; ``degraded`` means a
    non-critical dependency (a model server) is down; ``unavailable`` means a
    critical one is.
    """

    status: Literal["ready", "degraded", "unavailable"]
    app: str
    version: str
    environment: str
    checks: list[DependencyCheck] = Field(default_factory=list)
