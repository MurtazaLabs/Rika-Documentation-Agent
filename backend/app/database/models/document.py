"""Documents, their chunks and version history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import EMBEDDING_VECTOR_DIMENSION
from app.database.base import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
    json_type,
)
from app.database.models.enums import ContentType, DocumentStatus

if TYPE_CHECKING:
    from app.database.models.code import ProjectSymbol
    from app.database.models.job import IngestionJob
    from app.database.models.project import Project


class Document(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "original_path", name="uq_documents_project_path"),
        Index("ix_documents_project_id", "project_id"),
        Index("ix_documents_project_hash", "project_id", "content_hash"),
        Index("ix_documents_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Path as it appeared in the uploaded archive or folder.
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    # Path inside storage/, never exposed through the API.
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=DocumentStatus.PENDING.value, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    versions: Mapped[list[FileVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    symbols: Mapped[list[ProjectSymbol]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[IngestionJob]] = relationship(back_populates="document")


class DocumentChunk(UuidPrimaryKeyMixin, Base):
    __tablename__ = "document_chunks"
    # The PostgreSQL indexes that back retrieval are declared here so that
    # autogenerate compares them and can never emit a DROP for one. Both use
    # features SQLite lacks, so ``ddl_if`` keeps them out of the SQLite test
    # schema; migrations 0002 and 0003 own their production DDL.
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_index"
        ),
        Index("ix_document_chunks_project_id", "project_id"),
        Index("ix_document_chunks_project_symbol", "project_id", "symbol_name"),
        # Cosine HNSW over the fixed-width embedding column.
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ).ddl_if(dialect="postgresql"),
        # GIN over the generated tsvector column. The column itself is not
        # mapped: SQLite cannot create a generated column that calls
        # ``to_tsvector``, and unlike an Index a Column has no dialect
        # conditional DDL. Migration 0003 creates it and the autogenerate
        # filter in ``migrations/env.py`` keeps it out of comparisons.
        Index(
            "ix_document_chunks_search_vector",
            text("search_vector"),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Width is pinned by migration 0002 (and the HNSW index on the same
    # column); a chunk is only searchable once its vector is stored.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_VECTOR_DIMENSION), nullable=True
    )
    # Which embedding model produced the vector. Comparing vectors from two
    # different models is meaningless, so this travels with the chunk.
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(
        String(32), default=ContentType.DOCUMENT.value, nullable=False
    )
    language: Mapped[str | None] = mapped_column(String(64))
    symbol_name: Mapped[str | None] = mapped_column(String(255))
    start_line: Mapped[int | None] = mapped_column(Integer)
    end_line: Mapped[int | None] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", json_type(), default=dict, nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")


class FileVersion(UuidPrimaryKeyMixin, Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        Index("ix_file_versions_document_id", "document_id"),
        Index("ix_file_versions_document_created", "document_id", "created_at"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="versions")
