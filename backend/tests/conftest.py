"""Test fixtures.

The API is exercised through HTTP against an in-memory SQLite database with
the same models, so the default run needs no infrastructure.

Set ``RIKA_TEST_DATABASE_URL`` to run the same tests against a real database
whose schema was created by the migrations:

    $env:RIKA_TEST_DATABASE_URL="postgresql+asyncpg://rika:change-me@127.0.0.1:5432/rika"
    python -m pytest tests/test_projects.py

The schema then comes from Alembic rather than ``create_all``, so the tests
exercise the migrated tables -- pgvector, JSONB and database-level cascades --
and are truncated between tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.core.constants import EMBEDDING_VECTOR_DIMENSION
from app.database.base import Base
from app.database.session import get_session
from app.dependencies import get_chat_client, get_embedding_client
from app.main import app

EXTERNAL_DATABASE_URL = os.environ.get("RIKA_TEST_DATABASE_URL")


class FakeEmbeddingClient:
    """Stands in for the embedding server: deterministic vectors, no HTTP.

    Records every batch so tests can assert how the pipeline split the work.
    """

    model_name = "fake-embedding-model"

    def __init__(self, dimension: int = EMBEDDING_VECTOR_DIMENSION) -> None:
        self.dimension = dimension
        self.batches: list[list[str]] = []
        self.failure: Exception | None = None

    async def embed(self, texts):
        if self.failure is not None:
            raise self.failure
        self.batches.append(list(texts))
        return [
            [float(len(text) % 10) / 10.0] * self.dimension for text in texts
        ]


@pytest.fixture
def embeddings() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


class FakeChatClient:
    """Stands in for the chat server: scripted replies, no HTTP.

    ``calls`` keeps the exact messages the service built so tests can inspect
    the system prompt, retrieved context and conversation history.
    """

    model_name = "fake-chat-model"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.response = "The archive path is validated during ingestion [S1]."
        self.stream_chunks = [
            "The archive path is ",
            "validated during ingestion [S1].",
        ]
        self.failure: Exception | None = None
        self.stream_failure: Exception | None = None

    async def chat(self, messages, *, temperature=0.2, max_tokens=512):
        self._record(messages, temperature, max_tokens)
        if self.failure is not None:
            raise self.failure
        return self.response

    async def chat_stream(self, messages, *, temperature=0.2, max_tokens=512):
        self._record(messages, temperature, max_tokens)
        if self.stream_failure is not None:
            raise self.stream_failure
        for chunk in self.stream_chunks:
            yield chunk

    def _record(self, messages, temperature, max_tokens) -> None:
        self.calls.append(
            {
                "messages": [dict(message) for message in messages],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )


@pytest.fixture
def chat() -> FakeChatClient:
    return FakeChatClient()


@pytest.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    if EXTERNAL_DATABASE_URL:
        factory, engine = await _external_factory(EXTERNAL_DATABASE_URL)
    else:
        factory, engine = await _sqlite_factory()
    try:
        yield factory
    finally:
        await engine.dispose()


async def _sqlite_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def _external_factory(url: str):
    engine = create_async_engine(url)
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    except ProgrammingError as error:
        await engine.dispose()
        raise RuntimeError(
            f"RIKA_TEST_DATABASE_URL points at a database without the schema: {error.orig}. "
            "Run 'alembic upgrade head' against it first."
        ) from error
    return async_sessionmaker(engine, expire_on_commit=False), engine


@pytest.fixture
async def app_settings(tmp_path: Path) -> Settings:
    """Settings isolated to a temporary storage root with small limits."""
    settings = Settings(
        storage_root=tmp_path / "storage",
        max_upload_mb=2,
        max_archive_files=50,
        max_archive_expanded_mb=10,
        chunk_size_chars=400,
        chunk_overlap_chars=60,
        embedding_dimension=EMBEDDING_VECTOR_DIMENSION,
        embedding_batch_size=4,
        embedding_model_name=FakeEmbeddingClient.model_name,
    )
    for name in ("uploads", "temp"):
        (settings.storage_root / name).mkdir(parents=True, exist_ok=True)
    return settings


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    app_settings: Settings,
    embeddings: FakeEmbeddingClient,
    chat: FakeChatClient,
) -> AsyncClient:
    async def _session_override():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_settings] = lambda: app_settings
    app.dependency_overrides[get_embedding_client] = lambda: embeddings
    app.dependency_overrides[get_chat_client] = lambda: chat
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
