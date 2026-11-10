"""Declarative base and shared column helpers.

Models target PostgreSQL. ``json_type()`` keeps JSONB on PostgreSQL while
letting the test suite build the same schema on SQLite.
"""

from __future__ import annotations

import uuid as uuid_module
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, MetaData, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeEngine

# Deterministic constraint names keep Alembic migrations stable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def json_type() -> TypeEngine[Any]:
    """JSONB on PostgreSQL, JSON elsewhere (tests)."""
    return JSONB().with_variant(JSON(), "sqlite")


class UuidPrimaryKeyMixin:
    id: Mapped[uuid_module.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_module.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
