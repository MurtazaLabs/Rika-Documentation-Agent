"""Conversation persistence and project-scoped lookup.

Conversations belong to one project. Lookups accept an optional project id so
a workspace route can refuse a conversation that belongs elsewhere instead of
trusting a client-supplied id.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.models import Conversation, Message
from app.services.project_service import get_project

MAX_TITLE_CHARS = 120


async def create_conversation(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    title: str | None = None,
) -> Conversation:
    await get_project(session, project_id)
    conversation = Conversation(
        project_id=project_id,
        title=_clean_title(title) if title else None,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or (
        project_id is not None and conversation.project_id != project_id
    ):
        raise NotFoundError(f"Conversation {conversation_id} was not found")
    return conversation


async def get_conversation_with_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> tuple[Conversation, list[Message]]:
    conversation = await get_conversation(
        session, conversation_id, project_id=project_id
    )
    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.position, Message.created_at)
        )
    )
    return conversation, messages


async def list_conversations(
    session: AsyncSession,
    *,
    project_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Conversation, int]], int]:
    filters = []
    if project_id is not None:
        await get_project(session, project_id)
        filters.append(Conversation.project_id == project_id)

    total = await session.scalar(
        select(func.count(Conversation.id)).where(*filters)
    )

    statement = (
        select(Conversation, func.count(Message.id))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(*filters)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id)
        .limit(limit)
        .offset(offset)
    )
    rows = await session.execute(statement)
    return [(conversation, int(count)) for conversation, count in rows], int(
        total or 0
    )


async def delete_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> None:
    conversation = await get_conversation(
        session, conversation_id, project_id=project_id
    )
    await session.delete(conversation)
    await session.commit()


def derive_title(message: str) -> str:
    """A short, stable title from the first question."""
    text = " ".join(message.split())
    if not text:
        return "New conversation"
    if len(text) <= MAX_TITLE_CHARS:
        return text
    return text[: MAX_TITLE_CHARS - 3].rstrip() + "..."


def _clean_title(title: str) -> str:
    text = " ".join(title.split())
    if not text:
        return "New conversation"
    return text[:MAX_TITLE_CHARS]
