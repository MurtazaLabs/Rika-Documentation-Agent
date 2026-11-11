"""Read-only runtime configuration for the local settings page."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.schemas.settings import (
    AppSettingsRead,
    ChatSettings,
    EmbeddingSettings,
    IndexingSettings,
    StorageSettings,
)
from app.config import Settings, get_settings

router = APIRouter(tags=["settings"])


@router.get(
    "/settings",
    response_model=AppSettingsRead,
    summary="Read the running configuration",
    description=(
        "Returns the values the UI needs to explain how Rika is configured. "
        "Connection strings, credentials and CORS origins are never included. "
        "Editing .env requires restarting the API and model servers."
    ),
)
async def read_settings(settings: Settings = Depends(get_settings)) -> AppSettingsRead:
    return AppSettingsRead(
        app_name=settings.app_name,
        environment=settings.app_env,
        version=__version__,
        chat=ChatSettings(
            base_url=settings.chat_base_url,
            model_name=settings.chat_model_name,
            timeout_seconds=settings.chat_timeout,
            temperature=settings.chat_temperature,
            max_tokens=settings.chat_max_tokens,
            context_chunks=settings.chat_context_chunks,
            context_max_chars=settings.chat_context_max_chars,
            history_max_chars=settings.chat_history_max_chars,
            prompt_max_chars=settings.chat_prompt_max_chars,
        ),
        embedding=EmbeddingSettings(
            base_url=settings.embedding_base_url,
            model_name=settings.embedding_model_name,
            timeout_seconds=settings.embedding_timeout,
            dimension=settings.embedding_dimension,
            batch_size=settings.embedding_batch_size,
        ),
        storage=StorageSettings(
            root=str(settings.storage_root),
            max_upload_mb=settings.max_upload_mb,
            max_archive_files=settings.max_archive_files,
            max_archive_expanded_mb=settings.max_archive_expanded_mb,
        ),
        indexing=IndexingSettings(
            chunk_size_chars=settings.chunk_size_chars,
            chunk_overlap_chars=settings.chunk_overlap_chars,
        ),
    )
