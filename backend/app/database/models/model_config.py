"""Model identity and embedding dimension registry.

Embeddings from different models must never be compared, so each chunk's
embedding is tied to a recorded model identity and dimension.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UuidPrimaryKeyMixin, json_type


class ModelConfig(UuidPrimaryKeyMixin, Base):
    __tablename__ = "model_configs"
    __table_args__ = (
        UniqueConstraint(
            "model_name", "model_version", name="uq_model_configs_name_version"
        ),
    )

    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    configuration: Mapped[dict[str, Any]] = mapped_column(
        json_type(), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
