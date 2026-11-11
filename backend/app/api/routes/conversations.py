"""Conversation list, detail and deletion endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.conversation import (
    ConversationDetail,
    ConversationList,
    ConversationMessage,
    ConversationSummary,
)
from app.database.session import get_session
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get(
    "",
    response_model=ConversationList,
    summary="List conversations, newest first",
    description=(
        "Pass project_id to keep the list inside one project. Every item "
        "carries its project_id so a workspace can reject foreign entries."
    ),
)
async def list_conversations(
    project_id: uuid.UUID | None = Query(
        default=None,
        description="Only return conversations belonging to this project.",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ConversationList:
    rows, total = await conversation_service.list_conversations(
        session, project_id=project_id, limit=limit, offset=offset
    )
    return ConversationList(
        items=[
            ConversationSummary(
                id=conversation.id,
                project_id=conversation.project_id,
                title=conversation.title,
                message_count=message_count,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            for conversation, message_count in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="Read a conversation and its messages",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    project_id: uuid.UUID | None = Query(
        default=None,
        description="Reject the request if the conversation is not in this project.",
    ),
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    conversation, messages = (
        await conversation_service.get_conversation_with_messages(
            session, conversation_id, project_id=project_id
        )
    )
    return ConversationDetail(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            ConversationMessage(
                id=message.id,
                role=message.role,
                content=message.content,
                citations=message.citations,
                created_at=message.created_at,
            )
            for message in messages
        ],
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a conversation and its messages",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    project_id: uuid.UUID | None = Query(
        default=None,
        description="Reject the request if the conversation is not in this project.",
    ),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await conversation_service.delete_conversation(
        session, conversation_id, project_id=project_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
