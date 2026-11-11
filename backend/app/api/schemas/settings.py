"""Application settings exposed to the local UI.

Only values the dashboard and settings page need are returned. Connection
strings and credentials never leave the process, and the response is explicitly
read-only: these values come from ``.env`` and changing them requires a restart.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelServerSettings(BaseModel):
    base_url: str
    model_name: str
    timeout_seconds: float


class ChatSettings(ModelServerSettings):
    temperature: float
    max_tokens: int
    context_chunks: int
    context_max_chars: int
    history_max_chars: int
    prompt_max_chars: int


class EmbeddingSettings(ModelServerSettings):
    dimension: int | None = None
    batch_size: int


class StorageSettings(BaseModel):
    root: str
    max_upload_mb: int
    max_archive_files: int
    max_archive_expanded_mb: int


class IndexingSettings(BaseModel):
    chunk_size_chars: int
    chunk_overlap_chars: int


class AppSettingsRead(BaseModel):
    """Safe, read-only snapshot of the running configuration."""

    app_name: str
    environment: str
    version: str
    chat: ChatSettings
    embedding: EmbeddingSettings
    storage: StorageSettings
    indexing: IndexingSettings
    editable: bool = Field(
        default=False,
        description="Settings come from the environment and need a restart.",
    )
    source: str = ".env"
    restart_required: bool = True
