"""Initial schema for projects, documents and conversations.

Revision ID: 0001
Revises:
Create Date: 2026-11-09

Deliberate omissions, added in the phase that can justify them:

* the HNSW vector index on ``document_chunks.embedding`` — needs the verified
  embedding dimension (Phase 6);
* the generated ``tsvector`` column and GIN index for full-text search
  (Phase 7).

``embedding`` is therefore an unconstrained ``vector`` column for now.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    # pgvector must exist before document_chunks is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("original_path", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_documents_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint(
            "project_id", "original_path", name="uq_documents_project_path"
        ),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index(
        "ix_documents_project_hash", "documents", ["project_id", "content_hash"]
    )
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("symbol_name", sa.String(length=255), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_document_chunks_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunks_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_index"
        ),
    )
    op.create_index(
        "ix_document_chunks_project_id", "document_chunks", ["project_id"]
    )
    op.create_index(
        "ix_document_chunks_project_symbol",
        "document_chunks",
        ["project_id", "symbol_name"],
    )

    op.create_table(
        "file_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_file_versions_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_versions"),
    )
    op.create_index("ix_file_versions_document_id", "file_versions", ["document_id"])
    op.create_index(
        "ix_file_versions_document_created",
        "file_versions",
        ["document_id", "created_at"],
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_conversations_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
    )
    op.create_index("ix_conversations_project_id", "conversations", ["project_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_messages_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_ingestion_jobs_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_ingestion_jobs_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_jobs"),
    )
    op.create_index(
        "ix_ingestion_jobs_project_status", "ingestion_jobs", ["project_id", "status"]
    )
    op.create_index(
        "ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"]
    )

    op.create_table(
        "project_symbols",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("symbol_type", sa.String(length=32), nullable=False),
        sa.Column("symbol_name", sa.String(length=255), nullable=False),
        sa.Column("qualified_name", sa.String(length=512), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_symbols_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_project_symbols_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_symbols"),
    )
    op.create_index(
        "ix_project_symbols_project_name",
        "project_symbols",
        ["project_id", "symbol_name"],
    )
    op.create_index(
        "ix_project_symbols_project_type",
        "project_symbols",
        ["project_id", "symbol_type"],
    )
    op.create_index(
        "ix_project_symbols_document_id", "project_symbols", ["document_id"]
    )

    op.create_table(
        "project_dependencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("target_reference", sa.String(length=512), nullable=False),
        sa.Column("dependency_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_dependencies_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["documents.id"],
            name="fk_project_dependencies_source_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_dependencies"),
    )
    op.create_index(
        "ix_project_dependencies_project_type",
        "project_dependencies",
        ["project_id", "dependency_type"],
    )
    op.create_index(
        "ix_project_dependencies_source_document",
        "project_dependencies",
        ["source_document_id"],
    )

    op.create_table(
        "model_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("model_version", sa.String(length=200), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column(
            "configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_model_configs"),
        sa.UniqueConstraint(
            "model_name", "model_version", name="uq_model_configs_name_version"
        ),
    )


def downgrade() -> None:
    op.drop_table("model_configs")
    op.drop_table("project_dependencies")
    op.drop_table("project_symbols")
    op.drop_table("ingestion_jobs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("file_versions")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("projects")
    # The vector extension is left installed: other schemas may use it.
