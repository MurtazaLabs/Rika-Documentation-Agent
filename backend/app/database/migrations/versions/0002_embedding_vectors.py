"""Embedding vectors: fixed width, model identity and an HNSW index.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10

``check-models`` reports 1024 dimensions for Qwen3-Embedding-0.6B, and
``EMBEDDING_DIMENSION`` in ``.env`` is set to match. The width is written into
the migration as a literal because a schema revision must produce the same
database on every machine; ``app.core.constants.EMBEDDING_VECTOR_DIMENSION``
holds the same number for the ORM.

The index is cosine-distance HNSW, which is what the retrieval phase queries
(``embedding <=> $1``). Changing the embedding model therefore means changing
this schema revision and reindexing every chunk, not just restarting a server.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VECTOR_DIMENSION = 1024


def upgrade() -> None:
    op.alter_column(
        "document_chunks",
        "embedding",
        type_=Vector(VECTOR_DIMENSION),
        existing_type=Vector(),
        existing_nullable=True,
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
    )
    # Built after the column width is known; pgvector refuses HNSW on
    # unconstrained vectors.
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_column("document_chunks", "embedding_model")
    op.alter_column(
        "document_chunks",
        "embedding",
        type_=Vector(),
        existing_type=Vector(VECTOR_DIMENSION),
        existing_nullable=True,
    )
