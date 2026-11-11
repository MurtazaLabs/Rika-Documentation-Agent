"""Background ingestion job tracking."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.database.models.enums import JobStatus, JobType

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.project import Project


class IngestionJob(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index("ix_ingestion_jobs_project_status", "project_id", "status"),
        Index("ix_ingestion_jobs_document_id", "document_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    job_type: Mapped[str] = mapped_column(
        String(32), default=JobType.INGEST.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=JobStatus.QUEUED.value, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="jobs")
    document: Mapped[Document | None] = relationship(back_populates="jobs")
