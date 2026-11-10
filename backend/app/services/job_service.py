"""Ingestion job queries, queueing and retries.

The database row is the source of truth for progress; the queue is only a
delivery mechanism. An upload therefore succeeds even when the broker is down —
the job stays ``queued`` and ``POST /jobs/{id}/retry`` can push it again.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.database.models import Document, IngestionJob
from app.database.models.enums import DocumentStatus, JobStatus, JobType
from app.services.project_service import get_project

logger = logging.getLogger("rika.jobs")

RETRYABLE = {JobStatus.FAILED.value, JobStatus.CANCELLED.value}


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> IngestionJob:
    job = await session.get(IngestionJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} was not found")
    return job


async def list_project_jobs(
    session: AsyncSession, project_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[IngestionJob], int]:
    await get_project(session, project_id)
    scope = IngestionJob.project_id == project_id
    total = await session.scalar(select(func.count()).select_from(IngestionJob).where(scope))
    result = await session.scalars(
        select(IngestionJob)
        .where(scope)
        .order_by(IngestionJob.created_at.desc(), IngestionJob.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result), int(total or 0)


def enqueue_job(job_id: uuid.UUID) -> bool:
    """Hand a queued job to the worker. Never raises: the row keeps the state."""
    try:
        from app.workers.tasks import ingest_document

        ingest_document.delay(str(job_id))
        return True
    except Exception:  # noqa: BLE001 - broker errors must not lose the upload
        logger.warning("could not enqueue job %s; it stays queued", job_id, exc_info=True)
        return False


async def retry_job(session: AsyncSession, job_id: uuid.UUID) -> IngestionJob:
    job = await get_job(session, job_id)
    if job.status not in RETRYABLE:
        raise ConflictError(
            f"Job {job_id} is {job.status}; only failed or cancelled jobs can be retried"
        )
    job.status = JobStatus.QUEUED.value
    job.progress = 0
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    if job.document_id is not None:
        document = await session.get(Document, job.document_id)
        if document is not None:
            document.status = DocumentStatus.PENDING.value
    await session.commit()
    await session.refresh(job)
    return job


async def create_reindex_job(
    session: AsyncSession, document: Document
) -> IngestionJob:
    job = IngestionJob(
        project_id=document.project_id,
        document_id=document.id,
        job_type=JobType.REINDEX.value,
        status=JobStatus.QUEUED.value,
    )
    document.status = DocumentStatus.PENDING.value
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job
