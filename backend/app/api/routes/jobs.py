"""Ingestion job endpoints.

``GET /jobs/{id}`` is what a client polls for progress; ``POST /jobs/{id}/retry``
re-queues a failed job without re-uploading the file.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.job import JobList, JobRead
from app.database.session import get_session
from app.services import job_service

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobRead, summary="Get one job")
async def get_job(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> JobRead:
    return await job_service.get_job(session, job_id)


@router.get(
    "/projects/{project_id}/jobs",
    response_model=JobList,
    summary="List a project's jobs",
)
async def list_project_jobs(
    project_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> JobList:
    items, total = await job_service.list_project_jobs(
        session, project_id, limit=limit, offset=offset
    )
    return JobList(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-queue a failed job",
)
async def retry_job(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> JobRead:
    job = await job_service.retry_job(session, job_id)
    job_service.enqueue_job(job.id)
    return job
