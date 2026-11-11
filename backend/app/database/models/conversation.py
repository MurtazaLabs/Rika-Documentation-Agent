"""Conversations and their messages."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
    json_type,
)
from app.database.models.enums import MessageRole

if TYPE_CHECKING:
    from app.database.models.project import Project


class Conversation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_project_id", "project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(300))

    project: Mapped[Project] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.position",
    )


class Message(UuidPrimaryKeyMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_conversation_id_position", "conversation_id", "position"),
        UniqueConstraint(
            "conversation_id",
            "position",
            name="uq_messages_conversation_id_position",
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(32), default=MessageRole.USER.value, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Explicit ordering: created_at is the transaction timestamp on PostgreSQL,
    # so a question and its answer would otherwise share a value.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Citations are resolved against stored chunks before being saved, so the
    # UI never renders a source that was not retrieved.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        json_type(), default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
