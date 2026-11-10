"""Vector similarity search over ``document_chunks.embedding``.

PostgreSQL uses the pgvector cosine-distance operator (backed by the HNSW
index from migration ``0002``). SQLite has no vector type or operator, so the
test fallback computes cosine similarity in Python over the filtered project
chunks and returns the same score shape.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document, DocumentChunk
from app.retrieval._dialect import dialect_name
from app.retrieval.filters import build_sql_conditions
from app.retrieval.types import ChunkCandidate, SearchFilters

_COLUMNS = (
    DocumentChunk,
    Document.original_path,
    Document.filename,
    Document.file_type,
)


async def vector_search(
    session: AsyncSession,
    project_id: uuid.UUID,
    query_vector: Sequence[float],
    filters: SearchFilters,
    *,
    limit: int,
    embedding_model: str,
) -> list[ChunkCandidate]:
    """Return the nearest chunks, best first."""
    if dialect_name(session) == "postgresql":
        return await _postgres_vector_search(
            session,
            project_id,
            query_vector,
            filters,
            limit=limit,
            embedding_model=embedding_model,
        )
    return await _fallback_vector_search(
        session,
        project_id,
        query_vector,
        filters,
        limit=limit,
        embedding_model=embedding_model,
    )


async def _postgres_vector_search(
    session: AsyncSession,
    project_id: uuid.UUID,
    query_vector: Sequence[float],
    filters: SearchFilters,
    *,
    limit: int,
    embedding_model: str,
) -> list[ChunkCandidate]:
    distance = DocumentChunk.embedding.cosine_distance(list(query_vector))
    statement = (
        select(*_COLUMNS, distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            *build_sql_conditions(project_id, filters),
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_model == embedding_model,
        )
        .order_by(distance)
        .limit(limit)
    )

    rows = (await session.execute(statement)).all()
    return [
        _candidate(chunk, file_path, filename, file_type, 1.0 - float(score))
        for chunk, file_path, filename, file_type, score in rows
    ]


async def _fallback_vector_search(
    session: AsyncSession,
    project_id: uuid.UUID,
    query_vector: Sequence[float],
    filters: SearchFilters,
    *,
    limit: int,
    embedding_model: str,
) -> list[ChunkCandidate]:
    statement = (
        select(*_COLUMNS)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            *build_sql_conditions(project_id, filters, include_json=False),
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_model == embedding_model,
        )
    )
    rows = (await session.execute(statement)).all()

    candidates: list[ChunkCandidate] = []
    for chunk, file_path, filename, file_type in rows:
        stored = chunk.embedding or []
        if len(stored) != len(query_vector):
            continue
        score = _cosine_similarity(query_vector, stored)
        candidates.append(
            _candidate(chunk, file_path, filename, file_type, score)
        )

    candidates.sort(
        key=lambda item: (
            -float(item.vector_score or 0.0),
            item.chunk.chunk_index,
            str(item.chunk.id),
        )
    )
    return candidates[:limit]


def _candidate(
    chunk: DocumentChunk,
    file_path: str,
    filename: str,
    file_type: str,
    score: float,
) -> ChunkCandidate:
    return ChunkCandidate(
        chunk=chunk,
        file_path=file_path,
        filename=filename,
        file_type=file_type,
        vector_score=score,
    )


def _cosine_similarity(
    left: Sequence[float], right: Sequence[float]
) -> float:
    """Cosine similarity in ``[-1, 1]``; zero vectors score zero."""
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    similarity = dot / (left_norm * right_norm)
    return max(-1.0, min(1.0, similarity))
