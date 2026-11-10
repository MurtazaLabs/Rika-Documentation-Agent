"""Project-scoped SQL and in-memory metadata filters.

PostgreSQL queries use real SQL predicates on the joined ``documents`` row and
on the chunk's JSONB metadata. SQLite has no reliable JSON path operator across
versions, so the test fallback filters fetched chunks in Python with the same
semantics.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ColumnElement, func, or_

from app.database.models import Document, DocumentChunk
from app.retrieval.types import SearchFilters


def normalise_path(value: str) -> str:
    """Compare uploaded paths independently of Windows separators."""
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/")


def build_sql_conditions(
    project_id: uuid.UUID,
    filters: SearchFilters,
    *,
    include_json: bool = True,
) -> list[ColumnElement[bool]]:
    """Build the shared predicate for a retrieval query.

    Every call starts with the project boundary. File path and file type live
    on ``documents``; language, symbol type and document type live on the
    chunk (language may also be repeated in parser metadata).

    ``include_json=False`` is used by the SQLite fallback, which applies the
    metadata filters in Python instead of relying on JSON path support.
    """
    conditions: list[ColumnElement[bool]] = [
        DocumentChunk.project_id == project_id
    ]

    if filters.file_path:
        conditions.append(
            Document.original_path == normalise_path(filters.file_path)
        )

    if filters.file_type:
        conditions.append(
            func.lower(Document.file_type) == filters.file_type.lower()
        )

    if include_json and filters.language:
        language = filters.language.lower()
        conditions.append(
            or_(
                func.lower(DocumentChunk.language) == language,
                func.lower(
                    DocumentChunk.metadata_["language"].as_string()
                ) == language,
            )
        )

    if include_json and filters.symbol_type:
        conditions.append(
            func.lower(
                DocumentChunk.metadata_["symbol_type"].as_string()
            )
            == filters.symbol_type.lower()
        )

    directory = normalise_path(filters.directory or "")
    if directory == ".":
        directory = ""
    if directory:
        conditions.append(
            or_(
                Document.original_path == directory,
                Document.original_path.like(
                    f"{_like_escape(directory)}/%", escape="\\"
                ),
            )
        )

    if filters.document_type:
        conditions.append(
            func.lower(DocumentChunk.content_type)
            == filters.document_type.lower()
        )

    return conditions


def matches_filters(
    chunk: DocumentChunk,
    file_path: str,
    file_type: str,
    filters: SearchFilters,
) -> bool:
    """Apply :class:`SearchFilters` to an already-fetched chunk."""
    path = normalise_path(file_path)

    if filters.file_path and path != normalise_path(filters.file_path):
        return False

    if filters.file_type and file_type.lower() != filters.file_type.lower():
        return False

    if (
        filters.document_type
        and chunk.content_type.lower() != filters.document_type.lower()
    ):
        return False

    if filters.language:
        language = chunk.language or _metadata_text(chunk, "language")
        if not language or language.lower() != filters.language.lower():
            return False

    if filters.symbol_type:
        symbol_type = _metadata_text(chunk, "symbol_type")
        if (
            not symbol_type
            or symbol_type.lower() != filters.symbol_type.lower()
        ):
            return False

    directory = normalise_path(filters.directory or "")
    if directory == ".":
        directory = ""
    if directory and path != directory and not path.startswith(directory + "/"):
        return False

    return True


def _metadata_text(chunk: DocumentChunk, key: str) -> str | None:
    metadata: dict[str, Any] = chunk.metadata_ or {}
    value = metadata.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _like_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
