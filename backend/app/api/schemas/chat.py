"""Chat request and response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.api.schemas.search import SearchFilters


class ChatRequest(BaseModel):
    """A question scoped to the project in the URL."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Continue an existing conversation in this project.",
    )
    stream: bool = Field(
        default=False,
        description="Return server-sent events instead of one JSON response.",
    )
    filters: SearchFilters = Field(
        default_factory=SearchFilters,
        description="Optional metadata filters for evidence retrieval.",
    )

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("message must not be blank")
        return message


class ChatCitation(BaseModel):
    """A citation resolved against a retrieved chunk's stored metadata."""

    marker: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    file_path: str
    filename: str
    file_type: str
    content_type: str
    language: str | None = None
    symbol_name: str | None = None
    symbol_type: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    page_number: int | None = None
    snippet: str
    rank: int
    retrieval_score: float


class ChatIntelligenceItem(BaseModel):
    """A derived report item the answer relied on.

    These come from the stored index rather than a retrieved passage, so they
    carry a confidence label instead of a chunk id.
    """

    marker: str
    kind: str
    message: str
    confidence: str | None = None
    severity: str | None = None
    file_path: str | None = None
    line: int | None = None


class ChatResponse(BaseModel):
    project_id: uuid.UUID
    conversation_id: uuid.UUID
    user_message_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    intelligence: list[ChatIntelligenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retrieved_chunks: int
    grounded: bool
