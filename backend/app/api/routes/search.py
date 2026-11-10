"""Project-scoped retrieval endpoint."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.search import (
    SearchFilters as SearchFiltersSchema,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.config import Settings, get_settings
from app.database.session import get_session
from app.dependencies import get_embedding_client
from app.llm.llama_client import ModelServerClient
from app.retrieval.types import RetrievedChunk, SearchFilters
from app.services import retrieval_service

router = APIRouter(tags=["search"])


@router.post(
    "/projects/{project_id}/search",
    response_model=SearchResponse,
    summary="Search a project's indexed chunks",
    description=(
        "Hybrid retrieval by default: pgvector similarity and PostgreSQL "
        "full-text search fused with Reciprocal Rank Fusion. Results are "
        "always scoped to the project in the path and carry their citation."
    ),
)
async def search_project(
    project_id: uuid.UUID,
    payload: SearchRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    embedding_client: ModelServerClient = Depends(get_embedding_client),
) -> SearchResponse:
    filters = _to_filters(payload.filters)
    hits = await retrieval_service.search_project(
        session,
        project_id,
        query=payload.query,
        mode=payload.mode,
        limit=payload.limit,
        filters=filters,
        embedding_client=embedding_client,
        settings=settings,
    )
    items = [_to_result(hit) for hit in hits]
    return SearchResponse(
        query=payload.query,
        mode=payload.mode,
        project_id=project_id,
        items=items,
        total=len(items),
        limit=payload.limit,
    )


def _to_filters(filters: SearchFiltersSchema) -> SearchFilters:
    return SearchFilters(
        file_path=filters.file_path,
        file_type=filters.file_type,
        language=filters.language,
        symbol_type=filters.symbol_type,
        directory=filters.directory,
        document_type=filters.document_type,
    )


def _to_result(hit: RetrievedChunk) -> SearchResult:
    chunk = hit.chunk
    metadata = dict(chunk.metadata_ or {})
    return SearchResult(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        project_id=chunk.project_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        rank=hit.rank,
        score=hit.score,
        vector_score=hit.vector_score,
        keyword_score=hit.keyword_score,
        matched_by=list(hit.matched_by),
        file_path=hit.file_path,
        filename=hit.filename,
        file_type=hit.file_type,
        content_type=chunk.content_type,
        language=_optional_text(chunk.language or metadata.get("language")),
        symbol_name=chunk.symbol_name,
        symbol_type=_optional_text(metadata.get("symbol_type")),
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        page_number=chunk.page_number,
        metadata=metadata,
    )


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
