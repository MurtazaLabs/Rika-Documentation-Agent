"""Ingestion job schemas.

Progress is a percentage so the UI can render a bar without knowing the
pipeline's internal steps.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID | None
    job_type: str
    status: str
    progress: int
    attempts: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobList(BaseModel):
    items: list[JobRead]
    total: int
    limit: int
    offset: int
