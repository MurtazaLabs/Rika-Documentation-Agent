"""Document endpoints: metadata, deletion and re-indexing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.document import DocumentList, DocumentRead
from app.api.schemas.job import JobRead
from app.config import Settings, get_settings
from app.database.session import get_session
from app.services import document_service, job_service

router = APIRouter(tags=["documents"])


@router.get(
    "/projects/{project_id}/documents",
    response_model=DocumentList,
    summary="List a project's documents",
)
async def list_project_documents(
    project_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> DocumentList:
    items, total = await document_service.list_project_documents(
        session, project_id, limit=limit, offset=offset
    )
    return DocumentList(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRead,
    summary="Get document metadata",
)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentRead:
    return await document_service.get_document(session, document_id)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document, its chunks and its stored files",
)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    await document_service.delete_document(session, settings, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/documents/{document_id}/reindex",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run ingestion for a document",
)
async def reindex_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    document = await document_service.get_document(session, document_id)
    job = await job_service.create_reindex_job(session, document)
    job_service.enqueue_job(job.id)
    return job
