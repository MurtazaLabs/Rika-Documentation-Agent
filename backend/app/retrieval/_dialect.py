"""Small helper for keeping PostgreSQL-only SQL out of the SQLite test path."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


def dialect_name(session: AsyncSession) -> str:
    """Return the name of the session's SQL dialect (``postgresql``, ``sqlite``)."""
    bind = session.get_bind()
    return bind.dialect.name
