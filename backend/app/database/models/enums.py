"""Status and type values used by the models.

Stored as short strings so the schema stays portable and readable; Python
enums give the code names for the same values.
"""

from __future__ import annotations

from enum import Enum


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobType(str, Enum):
    INGEST = "ingest"
    REINDEX = "reindex"
    DELETE = "delete"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContentType(str, Enum):
    DOCUMENT = "document"
    CODE = "code"
