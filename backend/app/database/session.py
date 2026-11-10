"""Async database engine, session factory and request-scoped session."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from app.dependencies import AppResources, get_resources


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the async engine.

    The connect timeout sits just under ``READINESS_TIMEOUT`` so a refused
    connection is reported as such, rather than as a generic probe timeout.
    """
    connect_timeout = max(1.0, settings.readiness_timeout - 0.5)
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=3600,
        connect_args={"timeout": connect_timeout},
        echo=False,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session(
    resources: AppResources = Depends(get_resources),
) -> AsyncIterator[AsyncSession]:
    """Yield one session per request, rolling back on failure.

    Services commit explicitly, so a successful request ends after commit and
    a raised error never leaves a half-applied transaction behind.
    """
    async with resources.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
