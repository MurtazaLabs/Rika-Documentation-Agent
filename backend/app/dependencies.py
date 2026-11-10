"""Shared application resources and FastAPI accessors."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.exceptions import DependencyUnavailable
from app.llm.llama_client import ModelServerClient


@dataclass(slots=True)
class AppResources:
    """Long-lived clients created once per process in the lifespan."""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    chat_client: ModelServerClient
    embedding_client: ModelServerClient


def get_resources(request: Request) -> AppResources:
    """FastAPI dependency returning the resources bound to this app."""
    resources = getattr(request.app.state, "resources", None)
    if resources is None:  # pragma: no cover - only reachable if lifespan is skipped
        raise DependencyUnavailable("Application resources are not initialised")
    return resources


def get_embedding_client(request: Request) -> ModelServerClient:
    """FastAPI dependency for the shared embedding client.

    Kept separate from :func:`get_resources` so tests can substitute a
    deterministic client without starting the lifespan.
    """
    return get_resources(request).embedding_client
