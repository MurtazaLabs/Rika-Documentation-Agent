"""Application configuration.

Values come from environment variables, falling back to the ``.env`` file at the
repository root. Environment variables always win over the file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[2]

# Placeholder used in .env.example until the real embedding model is verified.
DIMENSION_PLACEHOLDER = "VERIFY_BEFORE_USE"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Rika"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Infrastructure
    database_url: str = "postgresql+asyncpg://rika:change-me@127.0.0.1:5432/rika"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # Local model servers (llama.cpp llama-server; any OpenAI-compatible server works)
    chat_base_url: str = "http://127.0.0.1:8080"
    chat_model_name: str = "local-chat-model"
    embedding_base_url: str = "http://127.0.0.1:8081"
    embedding_model_name: str = "local-embedding-model"
    # None until verified against the running embedding model. Ingestion refuses
    # to embed (and store) anything until it matches the vector column.
    embedding_dimension: int | None = None

    model_request_timeout: float = 30.0
    # Local chat generation is much slower than a metadata request, especially
    # with partial GPU offload, so it gets its own deadline.
    chat_timeout: float = 120.0
    # Embedding batches are much larger than a chat reply and run on the CPU,
    # so they get their own, more generous, deadline.
    embedding_timeout: float = 120.0
    readiness_timeout: float = 2.0
    # Simultaneous requests per model server. One slot matches the 4 GB GPU:
    # extra work waits in this process instead of queuing inside llama.cpp.
    chat_max_concurrency: int = 1
    embedding_max_concurrency: int = 1

    # Chat and RAG. Chunk and history budgets are characters rather than
    # tokens because the local model's tokenizer is not part of this service.
    chat_temperature: float = 0.2
    chat_max_tokens: int = 768
    chat_context_chunks: int = 8
    chat_context_max_chars: int = 6000
    chat_history_messages: int = 10
    chat_history_max_chars: int = 2000
    chat_retrieval_history_turns: int = 2
    # Whole-prompt ceiling. A 4K-context model needs room for the reply, so the
    # default leaves roughly 3K tokens for the prompt at ~4 characters/token.
    chat_prompt_max_chars: int = 12000
    chat_question_max_chars: int = 3000

    # Storage
    storage_root: Path = REPO_ROOT / "storage"
    max_upload_mb: int = 100
    max_archive_files: int = 5000
    max_archive_expanded_mb: int = 1000

    # Chunking (characters, not tokens: this is a local retrieval index, not a
    # model-specific tokenizer). Chunks are cut on line boundaries.
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 200
    # Chunks sent to /v1/embeddings per request.
    embedding_batch_size: int = 16

    # Frontend dev origins allowed to call the API
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    log_level: str = "INFO"

    @field_validator("embedding_dimension", mode="before")
    @classmethod
    def _parse_dimension(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned or cleaned.upper() == DIMENSION_PLACEHOLDER:
                return None
        return value

    @field_validator("storage_root", mode="before")
    @classmethod
    def _resolve_storage_root(cls, value: object) -> object:
        if value is None or value == "":
            return REPO_ROOT / "storage"
        path = Path(str(value)).expanduser()
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()

    @field_validator("embedding_batch_size")
    @classmethod
    def _check_batch_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be at least 1")
        return value

    @field_validator("chat_temperature")
    @classmethod
    def _check_temperature(cls, value: float) -> float:
        if not 0.0 <= value <= 2.0:
            raise ValueError("CHAT_TEMPERATURE must be between 0 and 2")
        return value

    @field_validator("chat_max_tokens", "chat_context_chunks")
    @classmethod
    def _check_positive_chat_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("chat token and context limits must be at least 1")
        return value

    @field_validator(
        "chat_context_max_chars",
        "chat_history_max_chars",
        "chat_timeout",
        "chat_prompt_max_chars",
        "chat_question_max_chars",
    )
    @classmethod
    def _check_positive_chat_budget(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("chat time and character budgets must be positive")
        return value

    @field_validator("chat_history_messages", "chat_retrieval_history_turns")
    @classmethod
    def _check_non_negative_chat_history(cls, value: int) -> int:
        if value < 0:
            raise ValueError("chat history limits must not be negative")
        return value

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return level

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def upload_limit_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def archive_expanded_limit_bytes(self) -> int:
        return self.max_archive_expanded_mb * 1024 * 1024

    @property
    def uploads_root(self) -> Path:
        return self.storage_root / "uploads"

    @property
    def temp_root(self) -> Path:
        return self.storage_root / "temp"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
