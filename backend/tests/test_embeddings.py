"""Embedding batching, dimension checks and failure behaviour."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.exceptions import ModelServerError
from app.database.models import Document, DocumentChunk, IngestionJob
from app.ingestion.embedding import EmbeddingError, batch_texts, embed_texts
from app.ingestion.pipeline import run_ingestion
from tests.conftest import FakeEmbeddingClient
from tests.test_uploads import create_project, quiet_queue, upload


def test_batches_split_on_count_and_characters() -> None:
    texts = ["a" * 10, "b" * 10, "c" * 10, "d" * 10]

    by_count = list(batch_texts(texts, batch_size=3, max_chars=10_000))
    assert [(start, batch) for start, batch in by_count] == [
        (0, texts[0:3]),
        (3, texts[3:4]),
    ]

    # A single oversized chunk is still sent on its own rather than dropped.
    by_chars = list(batch_texts(texts, batch_size=10, max_chars=25))
    assert [(start, batch) for start, batch in by_chars] == [
        (0, texts[0:2]),
        (2, texts[2:4]),
    ]


async def test_embed_texts_rejects_the_wrong_width() -> None:
    client = FakeEmbeddingClient(dimension=8)

    with pytest.raises(EmbeddingError) as error:
        await embed_texts(client, ["hello"], dimension=1024, batch_size=4)

    assert "1024" in str(error.value)


async def test_ingestion_embeds_every_chunk(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    text = "\n".join(f"row {number:03d} " + "z" * 40 for number in range(1, 41))
    response = await upload(client, project_id, "many.txt", text.encode())
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])

    async with session_factory() as session:
        result = await run_ingestion(session, job_id, app_settings, embeddings)

    assert result["status"] == "succeeded"
    async with session_factory() as session:
        chunks = (
            await session.scalars(select(DocumentChunk).order_by(DocumentChunk.chunk_index))
        ).all()
    assert len(chunks) == result["chunks"] > 1
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(len(chunk.embedding or []) == app_settings.embedding_dimension for chunk in chunks)
    assert {chunk.embedding_model for chunk in chunks} == {app_settings.embedding_model_name}


async def test_model_with_a_different_dimension_fails_the_job(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "wide.txt", b"content for a model swap\n")
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])
    wrong_model = FakeEmbeddingClient(dimension=768)

    async with session_factory() as session:
        result = await run_ingestion(session, job_id, app_settings, wrong_model)

    assert result["status"] == "failed"
    assert "1024" in result["error"]

    async with session_factory() as session:
        document = await session.get(Document, uuid.UUID(response.json()["items"][0]["document"]["id"]))
        assert document is not None and document.status == "failed"
        assert await session.scalar(select(DocumentChunk.id)) is None


async def test_unset_dimension_is_reported_not_guessed(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "unset.txt", b"text\n")
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])
    unset_settings = app_settings.model_copy(update={"embedding_dimension": None})

    async with session_factory() as session:
        result = await run_ingestion(session, job_id, unset_settings, embeddings)

    assert result["status"] == "failed"
    assert "EMBEDDING_DIMENSION" in result["error"]
    assert embeddings.batches == []


async def test_failed_reembedding_keeps_the_previous_chunks(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "stable.txt", b"stable content\n")
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])

    async with session_factory() as session:
        assert (await run_ingestion(session, job_id, app_settings, embeddings))["status"] == "succeeded"
    async with session_factory() as session:
        before = (await session.scalars(select(DocumentChunk))).all()
        assert before and before[0].embedding is not None

    embeddings.failure = ModelServerError("embedding server is down")
    async with session_factory() as session:
        job = await session.get(IngestionJob, job_id)
        assert job is not None
        job.status = "queued"  # a reindex reuses the same job record
        await session.commit()
    async with session_factory() as session:
        failed = await run_ingestion(session, job_id, app_settings, embeddings)

    assert failed["status"] == "failed"

    async with session_factory() as session:
        after = (await session.scalars(select(DocumentChunk))).all()
        assert [chunk.id for chunk in after] == [chunk.id for chunk in before]
        assert after[0].embedding == before[0].embedding
