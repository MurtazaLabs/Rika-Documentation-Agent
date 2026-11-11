"""Code intelligence: symbols and cross-file dependencies."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    UuidPrimaryKeyMixin,
    json_type,
)

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.project import Project


class ProjectSymbol(UuidPrimaryKeyMixin, Base):
    __tablename__ = "project_symbols"
    __table_args__ = (
        Index("ix_project_symbols_project_name", "project_id", "symbol_name"),
        Index("ix_project_symbols_project_type", "project_id", "symbol_type"),
        Index("ix_project_symbols_document_id", "document_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    symbol_type: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol_name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[str | None] = mapped_column(String(512))
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", json_type(), default=dict, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="symbols")
    document: Mapped[Document] = relationship(back_populates="symbols")


class ProjectDependency(UuidPrimaryKeyMixin, Base):
    __tablename__ = "project_dependencies"
    __table_args__ = (
        Index("ix_project_dependencies_project_type", "project_id", "dependency_type"),
        Index("ix_project_dependencies_source_document", "source_document_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # Import specifier as written in the source, e.g. "app.core.config".
    target_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(32), nullable=False)

    project: Mapped[Project] = relationship(back_populates="dependency_edges")
