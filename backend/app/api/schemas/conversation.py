"""Conversation list and detail schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.schemas.chat import ChatCitation

MessageRole = Literal["user", "assistant", "system"]


class ConversationMessage(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[ChatCitation] = Field(default_factory=list)
    created_at: datetime


class ConversationSummary(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationSummary] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class ConversationDetail(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessage] = Field(default_factory=list)
