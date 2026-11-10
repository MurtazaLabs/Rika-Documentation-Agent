"""Keyword search over indexed chunks.

PostgreSQL full-text search uses the generated ``search_vector`` column and
its GIN index from migration ``0003``. The query is parsed with
``websearch_to_tsquery`` and the ``simple`` configuration, which does not stem
or lowercase identifiers away: function names, routes and config keys stay
exact.

SQLite has no ``tsvector`` implementation, so the test fallback tokenises the
query and scores term hits in Python. Ranking and filtering semantics match
the PostgreSQL path, while the production path stays entirely in the database.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document, DocumentChunk
from app.retrieval._dialect import dialect_name
from app.retrieval.filters import build_sql_conditions, matches_filters
from app.retrieval.types import ChunkCandidate, SearchFilters

_COLUMNS = (
    DocumentChunk,
    Document.original_path,
    Document.filename,
    Document.file_type,
)

_TOKEN = re.compile(r"[\w][\w./:\\-]*", re.UNICODE)


async def keyword_search(
    session: AsyncSession,
    project_id: uuid.UUID,
    query: str,
    filters: SearchFilters,
    *,
    limit: int,
) -> list[ChunkCandidate]:
    """Return chunks matching the query's terms, best first."""
    if dialect_name(session) == "postgresql":
        return await _postgres_keyword_search(
            session, project_id, query, filters, limit=limit
        )
    return await _fallback_keyword_search(
        session, project_id, query, filters, limit=limit
    )


async def _postgres_keyword_search(
    session: AsyncSession,
    project_id: uuid.UUID,
    query: str,
    filters: SearchFilters,
    *,
    limit: int,
) -> list[ChunkCandidate]:
    search_vector = literal_column("document_chunks.search_vector")
    tsquery = func.websearch_to_tsquery(literal_column("'simple'"), query)
    rank = func.ts_rank_cd(search_vector, tsquery)

    statement = (
        select(*_COLUMNS, rank.label("rank"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            *build_sql_conditions(project_id, filters),
            search_vector.op("@@")(tsquery),
        )
        .order_by(rank.desc(), DocumentChunk.chunk_index)
        .limit(limit)
    )

    rows = (await session.execute(statement)).all()
    return [
        ChunkCandidate(
            chunk=chunk,
            file_path=file_path,
            filename=filename,
            file_type=file_type,
            keyword_score=float(score),
        )
        for chunk, file_path, filename, file_type, score in rows
    ]


async def _fallback_keyword_search(
    session: AsyncSession,
    project_id: uuid.UUID,
    query: str,
    filters: SearchFilters,
    *,
    limit: int,
) -> list[ChunkCandidate]:
    terms = _query_terms(query)
    if not terms:
        return []

    statement = (
        select(*_COLUMNS)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*build_sql_conditions(project_id, filters, include_json=False))
    )
    rows = (await session.execute(statement)).all()

    candidates: list[ChunkCandidate] = []
    for chunk, file_path, filename, file_type in rows:
        if not matches_filters(chunk, file_path, file_type, filters):
            continue
        score = _term_score(
            terms,
            content=chunk.content,
            symbol_name=chunk.symbol_name or "",
            file_path=file_path,
        )
        if score <= 0.0:
            continue
        candidates.append(
            ChunkCandidate(
                chunk=chunk,
                file_path=file_path,
                filename=filename,
                file_type=file_type,
                keyword_score=score,
            )
        )

    candidates.sort(
        key=lambda item: (
            -float(item.keyword_score or 0.0),
            item.chunk.chunk_index,
            str(item.chunk.id),
        )
    )
    return candidates[:limit]


def _query_terms(query: str) -> list[str]:
    """Split a query into lower-case identifier-friendly terms."""
    terms: list[str] = []
    for raw in _TOKEN.findall(query):
        term = raw.strip(".,;:!?/\\").lower()
        if term and term not in terms:
            terms.append(term)
    return terms


def _term_score(
    terms: list[str], *, content: str, symbol_name: str, file_path: str
) -> float:
    """Weight an exact symbol hit above body text, as the tsvector does."""
    content_lower = content.lower()
    symbol_lower = symbol_name.lower()
    path_lower = file_path.lower()
    score = 0.0
    for term in terms:
        if term in symbol_lower:
            score += 3.0
        if term in content_lower:
            score += 1.0
        if term in path_lower:
            score += 0.5
    return score
