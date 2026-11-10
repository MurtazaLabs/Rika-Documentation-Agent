"""Project CRUD.

Projects are the isolation boundary: every other table carries a
``project_id``, and queries are always scoped by it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.project import ProjectCreate, ProjectUpdate
from app.core.exceptions import NotFoundError
from app.database.models import Project


async def _require(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} was not found")
    return project


async def create_project(session: AsyncSession, payload: ProjectCreate) -> Project:
    project = Project(name=payload.name, description=payload.description)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Project], int]:
    total = await session.scalar(select(func.count()).select_from(Project))
    result = await session.scalars(
        select(Project)
        .order_by(Project.created_at.desc(), Project.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result), int(total or 0)


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    return await _require(session, project_id)


async def update_project(
    session: AsyncSession, project_id: uuid.UUID, payload: ProjectUpdate
) -> Project:
    project = await _require(session, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project_id: uuid.UUID) -> None:
    """Delete a project and, by cascade, everything stored under it."""
    project = await _require(session, project_id)
    await session.delete(project)
    await session.commit()
