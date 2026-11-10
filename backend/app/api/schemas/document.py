"""Document and upload schemas.

The server-side ``stored_path`` is deliberately not part of any response.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.job import JobRead


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    original_path: str
    filename: str
    file_type: str
    content_hash: str
    size: int
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int
    limit: int
    offset: int


class UploadedDocument(BaseModel):
    document: DocumentRead
    # Identical content already existed in this project; nothing was queued.
    duplicate: bool = False


class UploadResult(BaseModel):
    items: list[UploadedDocument]
    jobs: list[JobRead] = Field(default_factory=list)
    # Archive entries that were ignored because their extension is unsupported.
    skipped: list[str] = Field(default_factory=list)
