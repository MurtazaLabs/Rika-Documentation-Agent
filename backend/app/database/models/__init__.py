"""Database models.

Importing this package registers every table on ``Base.metadata``, which is
what Alembic compares against.
"""

from __future__ import annotations

from app.database.models.code import ProjectDependency, ProjectSymbol
from app.database.models.conversation import Conversation, Message
from app.database.models.document import Document, DocumentChunk, FileVersion
from app.database.models.enums import (
    ContentType,
    DocumentStatus,
    JobStatus,
    JobType,
    MessageRole,
)
from app.database.models.job import IngestionJob
from app.database.models.model_config import ModelConfig
from app.database.models.project import Project

__all__ = [
    "ContentType",
    "Conversation",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "FileVersion",
    "IngestionJob",
    "JobStatus",
    "JobType",
    "Message",
    "MessageRole",
    "ModelConfig",
    "Project",
    "ProjectDependency",
    "ProjectSymbol",
]
