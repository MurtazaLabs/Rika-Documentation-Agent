"""Upload endpoints.

Each upload is validated and stored synchronously (bounded by ``MAX_UPLOAD_MB``)
and then queued for parsing, so the response returns document and job ids even
while the worker is still processing.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.document import UploadedDocument, UploadResult
from app.config import Settings, get_settings
from app.core.exceptions import InvalidUploadError
from app.database.session import get_session
from app.services import job_service, upload_service

router = APIRouter(tags=["uploads"])


def _to_result(outcome: upload_service.UploadOutcome) -> UploadResult:
    return UploadResult(
        items=[
            UploadedDocument(document=document, duplicate=False)
            for document in outcome.documents
        ]
        + [
            UploadedDocument(document=document, duplicate=True)
            for document in outcome.duplicates
        ],
        jobs=outcome.jobs,
        skipped=outcome.skipped,
    )


def _enqueue(outcome: upload_service.UploadOutcome) -> None:
    for job in outcome.jobs:
        job_service.enqueue_job(job.id)


@router.post(
    "/projects/{project_id}/upload",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more files",
)
async def upload_files(
    project_id: uuid.UUID,
    files: list[UploadFile] = File(..., description="Files to ingest"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UploadResult:
    if not files:
        raise InvalidUploadError("No files were uploaded")
    outcome = await upload_service.ingest_uploads(
        session, settings, project_id, [(file, file.filename or "") for file in files]
    )
    _enqueue(outcome)
    return _to_result(outcome)


@router.post(
    "/projects/{project_id}/upload-folder",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a folder, keeping relative paths",
)
async def upload_folder(
    project_id: uuid.UUID,
    files: list[UploadFile] = File(..., description="Files from the folder"),
    paths: list[str] = Form(
        ..., description="Relative path of each file, in the same order as 'files'"
    ),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UploadResult:
    if len(files) != len(paths):
        raise InvalidUploadError(
            f"Received {len(files)} files but {len(paths)} paths; they must match"
        )
    outcome = await upload_service.ingest_uploads(
        session, settings, project_id, list(zip(files, paths))
    )
    _enqueue(outcome)
    return _to_result(outcome)


@router.post(
    "/projects/{project_id}/upload-zip",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a ZIP archive",
)
async def upload_zip(
    project_id: uuid.UUID,
    file: UploadFile = File(..., description="A .zip archive"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UploadResult:
    outcome = await upload_service.ingest_archive(session, settings, project_id, file)
    _enqueue(outcome)
    return _to_result(outcome)
