"""Search request and response schemas."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SearchMode = Literal["hybrid", "vector", "keyword"]
MatchedBy = Literal["vector", "keyword"]


class SearchFilters(BaseModel):
    """Metadata filters; every field is optional and combined with AND."""

    model_config = ConfigDict(extra="forbid")

    file_path: str | None = Field(
        default=None,
        max_length=4096,
        description="Exact uploaded file path, for example 'docs/setup.md'.",
    )
    file_type: str | None = Field(
        default=None,
        max_length=64,
        description="Document file type such as 'markdown', 'pdf' or 'code'.",
    )
    language: str | None = Field(
        default=None,
        max_length=64,
        description="Programming language, for example 'python'.",
    )
    symbol_type: str | None = Field(
        default=None,
        max_length=64,
        description="Code symbol type such as 'function', 'class' or 'method'.",
    )
    directory: str | None = Field(
        default=None,
        max_length=4096,
        description="Directory prefix, bounded at a path separator.",
    )
    document_type: str | None = Field(
        default=None,
        max_length=32,
        description="Chunk content type: 'document' or 'code'.",
    )

    @field_validator("*", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class SearchRequest(BaseModel):
    """A retrieval query scoped to the project in the URL."""

    query: str = Field(min_length=1, max_length=4000)
    mode: SearchMode = Field(
        default="hybrid",
        description="'hybrid' fuses both signals; other modes are for baseline comparison.",
    )
    limit: int = Field(default=10, ge=1, le=50)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("query must not be blank")
        return query


class SearchResult(BaseModel):
    """One ranked chunk with the citation needed to verify it."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    project_id: uuid.UUID
    chunk_index: int
    content: str

    rank: int
    score: float = Field(
        description="Final score: RRF in hybrid mode, otherwise the component score."
    )
    vector_score: float | None = Field(
        default=None, description="Cosine similarity when vector retrieval ran."
    )
    keyword_score: float | None = Field(
        default=None, description="Full-text rank when keyword retrieval ran."
    )
    matched_by: list[MatchedBy] = Field(default_factory=list)

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
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    project_id: uuid.UUID
    items: list[SearchResult] = Field(default_factory=list)
    total: int
    limit: int
