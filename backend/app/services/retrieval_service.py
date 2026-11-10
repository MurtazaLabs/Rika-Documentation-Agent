"""Orchestration for project-scoped hybrid retrieval.

This is the only place that calls the embedding server for a query. The
service enforces the project boundary before embedding anything, keeps the
candidate depth larger than the requested result count, and leaves reranking
out of the baseline.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.constants import EMBEDDING_VECTOR_DIMENSION
from app.core.exceptions import ConfigurationError, ModelServerError
from app.llm.llama_client import ModelServerClient
from app.retrieval.hybrid import rank_hits, reciprocal_rank_fusion
from app.retrieval.keyword_search import keyword_search
from app.retrieval.types import RetrievedChunk, SearchFilters
from app.retrieval.vector_search import vector_search
from app.services.project_service import get_project

VALID_MODES = frozenset({"hybrid", "vector", "keyword"})
MIN_CANDIDATES = 20
MAX_CANDIDATES = 200


async def search_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    query: str,
    mode: str,
    limit: int,
    filters: SearchFilters,
    embedding_client: ModelServerClient,
    settings: Settings,
) -> list[RetrievedChunk]:
    """Run vector and/or keyword search and return the best unique chunks."""
    # Resolve the project first: an unknown or foreign id must be a 404, and
    # it must not reach the embedding server.
    await get_project(session, project_id)

    text = query.strip()
    if not text:
        raise ValueError("query must not be empty")
    if mode not in VALID_MODES:
        raise ValueError(f"unsupported retrieval mode: {mode}")

    candidate_limit = min(max(limit * 4, MIN_CANDIDATES), MAX_CANDIDATES)
    vector_hits = []
    keyword_hits = []

    if mode in {"vector", "hybrid"}:
        query_vector = await _embed_query(embedding_client, text, settings)
        vector_hits = await vector_search(
            session,
            project_id,
            query_vector,
            filters,
            limit=candidate_limit,
            embedding_model=settings.embedding_model_name,
        )

    if mode in {"keyword", "hybrid"}:
        keyword_hits = await keyword_search(
            session,
            project_id,
            text,
            filters,
            limit=candidate_limit,
        )

    if mode == "vector":
        return rank_hits(vector_hits, source="vector", limit=limit)
    if mode == "keyword":
        return rank_hits(keyword_hits, source="keyword", limit=limit)
    return reciprocal_rank_fusion(
        vector_hits, keyword_hits, limit=limit
    )


async def _embed_query(
    client: ModelServerClient, query: str, settings: Settings
) -> list[float]:
    """Embed the query and refuse a vector wider than the stored column."""
    expected = EMBEDDING_VECTOR_DIMENSION
    if (
        settings.embedding_dimension is not None
        and settings.embedding_dimension != expected
    ):
        raise ConfigurationError(
            f"EMBEDDING_DIMENSION is {settings.embedding_dimension}, but "
            f"document_chunks.embedding is {expected} wide; correct .env and "
            "reindex before searching"
        )

    vectors = await client.embed([query])
    if len(vectors) != 1 or not vectors[0]:
        raise ModelServerError(
            "Embedding server did not return one query vector"
        )

    vector = vectors[0]
    if len(vector) != expected:
        raise ModelServerError(
            "Embedding server returned a "
            f"{len(vector)}-dimension query vector; document_chunks.embedding "
            f"is {expected} wide. Refusing to compare incompatible vectors."
        )
    return vector
