"""RAG orchestration: retrieval, prompt assembly, generation and persistence.

The service is deliberately separate from the routes. Non-streaming requests
raise normal application errors; streaming requests prepare everything before
the response starts (so 404s and retrieval failures are still HTTP errors) and
then turn generation failures into an SSE ``error`` event.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import AppError
from app.database.models import Conversation, Message, MessageRole
from app.intelligence.facts import load_facts
from app.llm.llama_client import ChatMessage, ModelServerClient
from app.rag.citations import CitationValidation, validate_citations
from app.rag.intelligence import (
    IntelligenceItem,
    IntelligenceValidation,
    build_intelligence,
    validate_intelligence,
)
from app.rag.prompts import build_chat_messages, build_retrieval_query
from app.rag.types import HistoryTurn, PromptSource
from app.retrieval.types import SearchFilters
from app.services import conversation_service, retrieval_service
from app.services.project_service import get_project

logger = logging.getLogger(__name__)

INSUFFICIENT_EVIDENCE_ANSWER = (
    "I couldn't find enough evidence in this project's indexed files to answer "
    "that question. Try rephrasing it, or upload and index the relevant files "
    "first."
)


@dataclass(slots=True)
class PreparedChat:
    """Everything needed to generate an answer, built before streaming starts."""

    project_id: uuid.UUID
    question: str
    conversation: Conversation
    created_conversation: bool
    history: list[HistoryTurn]
    messages: list[ChatMessage]
    sources: list[PromptSource]
    intelligence: list[IntelligenceItem]


@dataclass(slots=True)
class ChatAnswer:
    """A completed turn that has already been persisted."""

    project_id: uuid.UUID
    conversation: Conversation
    user_message: Message
    assistant_message: Message
    citations: list[dict[str, Any]]
    intelligence: list[dict[str, Any]]
    warnings: list[str]
    retrieved_chunks: int

    @property
    def grounded(self) -> bool:
        return bool(self.citations or self.intelligence)


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """One server-sent event from a streaming chat turn."""

    event: str
    data: dict[str, Any]


async def prepare_chat(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    message: str,
    conversation_id: uuid.UUID | None,
    filters: SearchFilters,
    embedding_client: ModelServerClient,
    settings: Settings,
) -> PreparedChat:
    """Resolve the project and conversation, retrieve evidence, build the prompt."""
    await get_project(session, project_id)

    created = conversation_id is None
    if created:
        conversation = await conversation_service.create_conversation(
            session,
            project_id,
            title=conversation_service.derive_title(message),
        )
    else:
        conversation = await conversation_service.get_conversation(
            session, conversation_id, project_id=project_id
        )
        if not conversation.title:
            conversation.title = conversation_service.derive_title(message)

    previous = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.position, Message.created_at)
        )
    )
    history = [
        HistoryTurn(role=item.role, content=item.content) for item in previous
    ]

    retrieval_query = build_retrieval_query(
        message,
        history,
        max_turns=settings.chat_retrieval_history_turns,
    )

    try:
        chunks = await retrieval_service.search_project(
            session,
            project_id,
            query=retrieval_query,
            mode="hybrid",
            limit=settings.chat_context_chunks,
            filters=filters,
            embedding_client=embedding_client,
            settings=settings,
        )
        prompt, sources, intelligence = build_chat_messages(
            message,
            history,
            chunks,
            intelligence=build_intelligence(
                await load_facts(session, project_id)
            ),
            max_context_chars=settings.chat_context_max_chars,
            max_history_messages=settings.chat_history_messages,
            max_history_chars=settings.chat_history_max_chars,
            max_prompt_chars=settings.chat_prompt_max_chars,
            max_question_chars=settings.chat_question_max_chars,
        )
    except Exception:
        if created:
            await _delete_empty_conversation(session, conversation.id)
        raise

    return PreparedChat(
        project_id=project_id,
        question=message,
        conversation=conversation,
        created_conversation=created,
        history=history,
        messages=prompt,
        sources=sources,
        intelligence=intelligence,
    )


async def answer_chat(
    session: AsyncSession,
    prepared: PreparedChat,
    *,
    chat_client: ModelServerClient,
    settings: Settings,
) -> ChatAnswer:
    """Generate a non-streaming answer and persist the turn."""
    if not prepared.sources and not prepared.intelligence:
        answer = INSUFFICIENT_EVIDENCE_ANSWER
        citations: list[dict[str, Any]] = []
        derived: list[dict[str, Any]] = []
        warnings = ["insufficient_evidence"]
    else:
        try:
            raw = await chat_client.chat(
                prepared.messages,
                temperature=settings.chat_temperature,
                max_tokens=settings.chat_max_tokens,
            )
        except Exception:
            if prepared.created_conversation:
                await _delete_empty_conversation(
                    session, prepared.conversation.id
                )
            raise

        validation = validate_citations(raw, prepared.sources)
        answer, citations, derived, warnings = _finalise_answer(
            validation,
            validate_intelligence(validation.text, prepared.intelligence),
        )

    user_message, assistant_message = await _persist_turn(
        session, prepared, answer, citations
    )
    return ChatAnswer(
        project_id=prepared.project_id,
        conversation=prepared.conversation,
        user_message=user_message,
        assistant_message=assistant_message,
        citations=citations,
        intelligence=derived,
        warnings=warnings,
        retrieved_chunks=len(prepared.sources),
    )


async def stream_answer(
    session: AsyncSession,
    prepared: PreparedChat,
    *,
    chat_client: ModelServerClient,
    settings: Settings,
) -> AsyncIterator[StreamEvent]:
    """Generate a streaming turn as start/token/citations/done events.

    Preparation has already happened, so the only failures here occur after
    the response has started. They are reported as an ``error`` event and any
    new, still-empty conversation is removed.
    """
    yield StreamEvent(
        "start",
        {
            "project_id": str(prepared.project_id),
            "conversation_id": str(prepared.conversation.id),
            "retrieved_chunks": len(prepared.sources),
        },
    )

    completed = False
    try:
        if not prepared.sources and not prepared.intelligence:
            answer = INSUFFICIENT_EVIDENCE_ANSWER
            citations: list[dict[str, Any]] = []
            derived: list[dict[str, Any]] = []
            warnings = ["insufficient_evidence"]
            yield StreamEvent("token", {"delta": answer})
        else:
            parts: list[str] = []
            async for delta in chat_client.chat_stream(
                prepared.messages,
                temperature=settings.chat_temperature,
                max_tokens=settings.chat_max_tokens,
            ):
                parts.append(delta)
                yield StreamEvent("token", {"delta": delta})

            raw = "".join(parts)
            validation = validate_citations(raw, prepared.sources)
            answer, citations, derived, warnings = _finalise_answer(
                validation,
                validate_intelligence(validation.text, prepared.intelligence),
            )
            if not raw.strip():
                yield StreamEvent("token", {"delta": answer})

        user_message, assistant_message = await _persist_turn(
            session, prepared, answer, citations
        )
        completed = True
        yield StreamEvent("citations", {"citations": citations})
        yield StreamEvent(
            "done",
            _turn_payload(
                prepared,
                user_message,
                assistant_message,
                answer,
                citations,
                derived,
                warnings,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - must become an SSE event
        logger.exception("streaming chat turn failed")
        yield StreamEvent("error", _error_payload(exc))
    finally:
        if not completed:
            await _cleanup_after_stream_failure(session, prepared)


async def _persist_turn(
    session: AsyncSession,
    prepared: PreparedChat,
    answer: str,
    citations: list[dict[str, Any]],
) -> tuple[Message, Message]:
    last_position = await session.scalar(
        select(func.coalesce(func.max(Message.position), -1)).where(
            Message.conversation_id == prepared.conversation.id
        )
    )
    position = int(last_position if last_position is not None else -1) + 1

    user_message = Message(
        conversation_id=prepared.conversation.id,
        role=MessageRole.USER.value,
        content=prepared.question,
        position=position,
        citations=[],
    )
    assistant_message = Message(
        conversation_id=prepared.conversation.id,
        role=MessageRole.ASSISTANT.value,
        content=answer,
        position=position + 1,
        citations=citations,
    )
    session.add_all([user_message, assistant_message])
    await session.execute(
        update(Conversation)
        .where(Conversation.id == prepared.conversation.id)
        .values(updated_at=func.now())
    )
    await session.commit()
    await session.refresh(user_message)
    await session.refresh(assistant_message)
    await session.refresh(prepared.conversation)
    return user_message, assistant_message


def _finalise_answer(
    validation: CitationValidation,
    derived: IntelligenceValidation,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not derived.text.strip():
        # The model produced nothing, or only invented markers. Saying so is
        # more honest than presenting an empty answer as grounded.
        return (
            INSUFFICIENT_EVIDENCE_ANSWER,
            [],
            [],
            ["insufficient_evidence", "empty_model_answer"],
        )

    if validation.invalid_markers:
        warnings.append("invalid_citations_removed")
    if derived.invalid_markers:
        warnings.append("invalid_intelligence_markers_removed")
    if not validation.citations and not derived.items:
        warnings.append("no_valid_citations")
    return derived.text, validation.citations, derived.items, warnings


def _turn_payload(
    prepared: PreparedChat,
    user_message: Message,
    assistant_message: Message,
    answer: str,
    citations: list[dict[str, Any]],
    intelligence: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "project_id": str(prepared.project_id),
        "conversation_id": str(prepared.conversation.id),
        "user_message_id": str(user_message.id),
        "message_id": str(assistant_message.id),
        "answer": answer,
        "citations": citations,
        "intelligence": intelligence,
        "warnings": warnings,
        "retrieved_chunks": len(prepared.sources),
        "grounded": bool(citations or intelligence),
    }


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, AppError):
        return {"code": exc.code, "message": exc.message}
    return {
        "code": "internal_error",
        "message": "An unexpected error occurred while generating the answer",
    }


async def _delete_empty_conversation(
    session: AsyncSession, conversation_id: uuid.UUID
) -> None:
    """Remove a conversation created for a turn that failed before saving."""
    try:
        await session.rollback()
        message_count = await session.scalar(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id
            )
        )
        if message_count:
            return
        conversation = await session.get(Conversation, conversation_id)
        if conversation is not None:
            await session.delete(conversation)
            await session.commit()
    except Exception:  # pragma: no cover - cleanup must not mask the real error
        logger.exception("could not remove empty failed conversation")


async def _cleanup_after_stream_failure(
    session: AsyncSession, prepared: PreparedChat
) -> None:
    if prepared.created_conversation:
        await _delete_empty_conversation(session, prepared.conversation.id)
    else:
        try:
            await session.rollback()
        except Exception:  # pragma: no cover - defensive
            logger.exception("could not roll back a failed chat turn")
