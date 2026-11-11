"""Stable message ordering within a conversation.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11

``messages.created_at`` is a database server default. On PostgreSQL that is the
transaction timestamp, so a question and the answer saved in the same
transaction receive the same value and cannot be ordered reliably. Chat turns
need a deterministic order, so each message gets a per-conversation position.

Existing rows are numbered by their old timestamp order before the unique
constraint is created; new rows are assigned the next position by
``app.services.chat_service``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Backfill in timestamp order (id breaks ties) before enforcing uniqueness.
    op.execute(
        """
        UPDATE messages AS message
        SET position = ranked.position
        FROM (
            SELECT
                id,
                (row_number() OVER (
                    PARTITION BY conversation_id
                    ORDER BY created_at, id
                ) - 1)::integer AS position
            FROM messages
        ) AS ranked
        WHERE message.id = ranked.id
        """
    )

    op.create_index(
        "ix_messages_conversation_id_position",
        "messages",
        ["conversation_id", "position"],
    )
    op.create_unique_constraint(
        "uq_messages_conversation_id_position",
        "messages",
        ["conversation_id", "position"],
    )
    op.alter_column("messages", "position", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "uq_messages_conversation_id_position", "messages", type_="unique"
    )
    op.drop_index("ix_messages_conversation_id_position", table_name="messages")
    op.drop_column("messages", "position")
