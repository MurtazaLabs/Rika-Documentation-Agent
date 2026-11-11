"""Document metadata, deletion and re-indexing.

Listing always goes through the owning project, so an unknown or foreign
project id can never leak another project's documents.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import NotFoundError
from app.database.models import Document, DocumentChunk, IngestionJob
from app.ingestion.formats import format_for
from app.services.project_service import get_project

logger = logging.getLogger("rika.documents")

# Large enough for ordinary source files, small enough that a browser can
# render the result without freezing. The UI says when content was cut.
PREVIEW_MAX_CHARS = 400_000
_PREVIEW_MAX_BYTES = PREVIEW_MAX_CHARS * 4 + 1
TEXTUAL_FILE_TYPES = frozenset(
    {"text", "markdown", "json", "yaml", "toml", "xml", "csv", "html", "code"}
)


async def list_project_documents(
    session: AsyncSession, project_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Document], int]:
    await get_project(session, project_id)
    scope = Document.project_id == project_id
    total = await session.scalar(select(func.count()).select_from(Document).where(scope))
    result = await session.scalars(
        select(Document)
        .where(scope)
        .order_by(Document.original_path)
        .limit(limit)
        .offset(offset)
    )
    return list(result), int(total or 0)


async def get_document(session: AsyncSession, document_id: uuid.UUID) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise NotFoundError(f"Document {document_id} was not found")
    return document


async def preview_document(
    session: AsyncSession,
    settings: Settings,
    document_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Return a safe text preview of a document.

    Text and code are read from the stored upload. PDFs and office files have
    no viewable source, so their indexed chunks are reconstructed instead.
    The stored path is checked against the storage root before any read.
    """
    document = await get_document(session, document_id)
    if project_id is not None and document.project_id != project_id:
        raise NotFoundError(f"Document {document_id} was not found")

    format_ = format_for(document.original_path)
    preview: dict[str, Any] = {
        "document_id": document.id,
        "project_id": document.project_id,
        "file_path": document.original_path,
        "filename": document.filename,
        "file_type": document.file_type,
        "language": format_.language if format_ is not None else None,
        "source": "none",
        "content": "",
        "line_count": None,
        "truncated": False,
        "message": None,
    }

    if document.file_type in TEXTUAL_FILE_TYPES:
        path = _safe_stored_path(settings, document.stored_path)
        if path is not None and path.is_file():
            content, truncated = _read_preview_text(path)
            preview.update(
                source="file",
                content=content,
                line_count=len(content.splitlines()) if content else 0,
                truncated=truncated,
                message=(
                    "Preview truncated to the first "
                    f"{PREVIEW_MAX_CHARS:,} characters."
                    if truncated
                    else None
                ),
            )
            return preview

    chunks = list(
        await session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        )
    )
    if not chunks:
        preview["message"] = (
            "This document has not been indexed yet, so there is no preview."
        )
        return preview

    pieces: list[str] = []
    for chunk in chunks:
        if chunk.page_number is not None:
            label = f"[page {chunk.page_number}]"
        elif chunk.start_line is not None and chunk.end_line is not None:
            label = f"[lines {chunk.start_line}-{chunk.end_line}]"
        else:
            label = f"[chunk {chunk.chunk_index + 1}]"
        pieces.append(f"{label}\n{chunk.content}")
    content = "\n\n".join(pieces)
    truncated = len(content) > PREVIEW_MAX_CHARS
    if truncated:
        content = content[:PREVIEW_MAX_CHARS].rstrip() + "\n\n[preview truncated]"

    preview.update(
        source="chunks",
        content=content,
        language=preview["language"] or (chunks[0].language if chunks else None),
        truncated=truncated,
        message=(
            "The original file is not plain text. This preview is "
            "reconstructed from indexed chunks, so line numbers refer to "
            "each chunk's stored range."
        ),
    )
    return preview


def _safe_stored_path(settings: Settings, stored_path: str) -> Path | None:
    """Resolve a stored path, refusing anything outside the storage root."""
    root = settings.storage_root.resolve()
    candidate = (settings.storage_root / stored_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        logger.warning("refused document preview outside storage root")
        return None
    return candidate


def _read_preview_text(path: Path) -> tuple[str, bool]:
    with path.open("rb") as handle:
        raw = handle.read(_PREVIEW_MAX_BYTES)
    truncated = len(raw) >= _PREVIEW_MAX_BYTES
    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > PREVIEW_MAX_CHARS:
        text = text[:PREVIEW_MAX_CHARS]
        truncated = True
    return text, truncated


async def delete_document(
    session: AsyncSession, settings: Settings, document_id: uuid.UUID
) -> None:
    """Remove the document, its chunks and its stored files."""
    document = await get_document(session, document_id)
    project_id = document.project_id
    stored_id = document.id

    # Jobs reference the document without an ORM cascade, and SQLite tests run
    # without foreign-key enforcement, so remove them explicitly.
    await session.execute(
        delete(IngestionJob).where(IngestionJob.document_id == stored_id)
    )
    await session.delete(document)
    await session.commit()

    document_dir = settings.uploads_root / str(project_id) / str(stored_id)
    shutil.rmtree(document_dir, ignore_errors=True)
    logger.info("deleted document %s from project %s", stored_id, project_id)
