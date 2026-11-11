"""Project endpoints under ``/api/v1/projects``."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.api.schemas.project import (
    ProjectCreate,
    ProjectList,
    ProjectRead,
    ProjectUpdate,
)
from app.database.session import get_session
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    return await project_service.create_project(session, payload)


@router.get("", response_model=ProjectList, summary="List projects")
async def list_projects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ProjectList:
    items, total = await project_service.list_projects(
        session, limit=limit, offset=offset
    )
    return ProjectList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{project_id}", response_model=ProjectRead, summary="Get a project")
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    return await project_service.get_project(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead, summary="Update a project")
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    return await project_service.update_project(session, project_id, payload)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a project and everything stored under it",
)
async def delete_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    await project_service.delete_project(session, settings, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
