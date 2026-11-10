"""Full-text search: generated tsvector column and GIN index.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10

Keyword retrieval needs exact identifiers, routes, error messages and config
keys. A stored generated column keeps the tsvector automatically in sync with
each chunk write, so ingestion does not need a second update and re-indexing
cannot leave a stale index behind.

The ``simple`` configuration is deliberate: it tokenises without stemming, so
``authenticate_user`` stays one searchable identifier. Symbol names, content
and the source path are weighted A, B and C respectively; the matching
retrieval query lives in ``app.retrieval.keyword_search``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(symbol_name, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(content, '')), 'B') ||
            setweight(
                to_tsvector(
                    'simple',
                    coalesce(metadata ->> 'file_path', '')
                ),
                'C'
            )
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_search_vector "
        "ON document_chunks USING gin (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_vector")
