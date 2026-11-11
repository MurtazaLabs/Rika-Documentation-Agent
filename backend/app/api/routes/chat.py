"""Project-scoped chat endpoint with optional SSE streaming."""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.chat import ChatRequest, ChatResponse
from app.config import Settings, get_settings
from app.database.session import get_session
from app.dependencies import get_chat_client, get_embedding_client
from app.llm.llama_client import ModelServerClient
from app.retrieval.types import SearchFilters
from app.services import chat_service

router = APIRouter(tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post(
    "/projects/{project_id}/chat",
    response_model=ChatResponse,
    summary="Ask Rika about a project",
    description=(
        "Retrieves project evidence, answers with validated citations and "
        "persists the turn in a conversation. Set stream=true for "
        "text/event-stream responses."
    ),
    responses={
        200: {
            "description": "One JSON answer, or SSE events when stream=true.",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "example": (
                        "event: start\n"
                        'data: {"conversation_id":"...","retrieved_chunks":3}\n\n'
                        "event: token\n"
                        'data: {"delta":"The archive path is checked in "}\n\n'
                        "event: citations\n"
                        'data: {"citations":[...]}\n\n'
                        "event: done\n"
                        'data: {"answer":"...","citations":[...]}\n\n'
                    ),
                }
            },
        }
    },
)
async def chat(
    project_id: uuid.UUID,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    chat_client: ModelServerClient = Depends(get_chat_client),
    embedding_client: ModelServerClient = Depends(get_embedding_client),
) -> ChatResponse | StreamingResponse:
    prepared = await chat_service.prepare_chat(
        session,
        project_id,
        message=payload.message,
        conversation_id=payload.conversation_id,
        filters=SearchFilters(**payload.filters.model_dump()),
        embedding_client=embedding_client,
        settings=settings,
    )

    if payload.stream:
        return StreamingResponse(
            _stream_events(prepared, session, chat_client, settings),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    answer = await chat_service.answer_chat(
        session, prepared, chat_client=chat_client, settings=settings
    )
    return _response(answer)


async def _stream_events(
    prepared: chat_service.PreparedChat,
    session: AsyncSession,
    chat_client: ModelServerClient,
    settings: Settings,
) -> AsyncIterator[str]:
    async for event in chat_service.stream_answer(
        session, prepared, chat_client=chat_client, settings=settings
    ):
        yield _sse(event.event, event.data)


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _response(answer: chat_service.ChatAnswer) -> ChatResponse:
    return ChatResponse(
        project_id=answer.project_id,
        conversation_id=answer.conversation.id,
        user_message_id=answer.user_message.id,
        message_id=answer.assistant_message.id,
        answer=answer.assistant_message.content,
        citations=answer.citations,
        warnings=answer.warnings,
        retrieved_chunks=answer.retrieved_chunks,
        grounded=answer.grounded,
    )
