"""Document metadata, deletion and re-indexing.

Listing always goes through the owning project, so an unknown or foreign
project id can never leak another project's documents.
"""

from __future__ import annotations

import logging
import shutil
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import NotFoundError
from app.database.models import Document, IngestionJob
from app.services.project_service import get_project

logger = logging.getLogger("rika.documents")


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
