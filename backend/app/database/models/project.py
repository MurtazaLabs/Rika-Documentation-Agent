"""Projects: the isolation boundary for every stored artifact."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
    json_type,
)

if TYPE_CHECKING:
    from app.database.models.code import ProjectDependency, ProjectSymbol
    from app.database.models.conversation import Conversation
    from app.database.models.document import Document
    from app.database.models.job import IngestionJob


class Project(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict[str, Any]] = mapped_column(
        json_type(), default=dict, nullable=False
    )

    documents: Mapped[list[Document]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    symbols: Mapped[list[ProjectSymbol]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    dependency_edges: Mapped[list[ProjectDependency]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[IngestionJob]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
