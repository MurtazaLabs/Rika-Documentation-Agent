"""Hybrid retrieval: ranking, filters, project scope and validation."""

from __future__ import annotations

import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.core.constants import EMBEDDING_VECTOR_DIMENSION
from app.database.models import Document, DocumentChunk
from app.dependencies import get_embedding_client
from app.main import app
from app.retrieval.filters import matches_filters
from app.retrieval.hybrid import reciprocal_rank_fusion
from app.retrieval.types import ChunkCandidate, SearchFilters
from tests.conftest import FakeEmbeddingClient


class StaticEmbeddingClient:
    """Returns one pre-built query vector, regardless of the input text."""

    model_name = FakeEmbeddingClient.model_name

    def __init__(self, vector: list[float]) -> None:
        self.vector = list(vector)
        self.batches: list[list[str]] = []

    async def embed(self, texts):
        self.batches.append(list(texts))
        return [list(self.vector) for _ in texts]


class FailingEmbeddingClient:
    """Fails the test if keyword-only search calls the embedding server."""

    model_name = FakeEmbeddingClient.model_name

    async def embed(self, texts):
        raise AssertionError("keyword-only search must not embed the query")


def vector(*values: float) -> list[float]:
    return list(values) + [0.0] * (EMBEDDING_VECTOR_DIMENSION - len(values))


async def create_project(client: AsyncClient, name: str = "Retrieval") -> str:
    response = await client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def create_document(
    session: AsyncSession,
    project_id: str,
    path: str,
    *,
    file_type: str = "code",
) -> Document:
    digest = hashlib.sha256(f"{project_id}:{path}".encode()).hexdigest()
    document = Document(
        project_id=uuid.UUID(project_id),
        original_path=path,
        stored_path=f"{project_id}/{digest}",
        filename=path.rsplit("/", 1)[-1],
        file_type=file_type,
        content_hash=digest,
        size=1,
        status="indexed",
    )
    session.add(document)
    await session.flush()
    return document


async def add_chunk(
    session: AsyncSession,
    document: Document,
    index: int,
    content: str,
    *,
    embedding: list[float] | None = None,
    content_type: str = "code",
    language: str | None = "python",
    symbol_name: str | None = None,
    symbol_type: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
    page_number: int | None = None,
    metadata: dict | None = None,
) -> DocumentChunk:
    data = {
        "file_path": document.original_path,
        "file_type": document.file_type,
    }
    if language:
        data["language"] = language
    if symbol_type:
        data["symbol_type"] = symbol_type
    if metadata:
        data.update(metadata)
    chunk = DocumentChunk(
        project_id=document.project_id,
        document_id=document.id,
        chunk_index=index,
        content=content,
        embedding=embedding,
        embedding_model=FakeEmbeddingClient.model_name,
        content_type=content_type,
        language=language,
        symbol_name=symbol_name,
        start_line=start_line,
        end_line=end_line,
        page_number=page_number,
        metadata_=data,
    )
    session.add(chunk)
    await session.flush()
    return chunk


async def test_hybrid_search_fuses_signals_and_cites_every_field(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project_id = await create_project(client)
    async with session_factory() as session:
        document = await create_document(session, project_id, "src/auth.py")
        exact = await add_chunk(
            session,
            document,
            0,
            "def authenticate_user(password):\n    return check_hash(password)",
            embedding=vector(1.0),
            symbol_name="authenticate_user",
            symbol_type="function",
            start_line=10,
            end_line=20,
        )
        near = await add_chunk(
            session,
            document,
            1,
            "def login_route():\n    return '/api/v1/login'",
            embedding=vector(0.9, 0.1),
            symbol_name="login_route",
            symbol_type="function",
            start_line=22,
            end_line=24,
        )
        far = await add_chunk(
            session,
            document,
            2,
            "release notes and unrelated prose",
            embedding=vector(0.0, 1.0),
            content_type="document",
            language=None,
            page_number=3,
        )
        await session.commit()
        exact_id = str(exact.id)
        near_id = str(near.id)
        far_id = str(far.id)

    app.dependency_overrides[get_embedding_client] = lambda: StaticEmbeddingClient(
        vector(1.0)
    )
    response = await client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "authenticate_user", "limit": 5},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    items = body["items"]
    assert body["total"] == len(items) == 3
    assert [item["chunk_id"] for item in items] == [exact_id, near_id, far_id]
    assert len({item["chunk_id"] for item in items}) == len(items)
    assert items[0]["rank"] == 1

    first = items[0]
    assert first["matched_by"] == ["vector", "keyword"]
    assert first["score"] > items[1]["score"] > items[2]["score"]
    assert first["vector_score"] == pytest.approx(1.0)
    assert first["keyword_score"] is not None
    assert first["file_path"] == "src/auth.py"
    assert first["filename"] == "auth.py"
    assert first["file_type"] == "code"
    assert first["content_type"] == "code"
    assert first["language"] == "python"
    assert first["symbol_name"] == "authenticate_user"
    assert first["symbol_type"] == "function"
    assert first["start_line"] == 10
    assert first["end_line"] == 20
    assert first["metadata"]["file_path"] == "src/auth.py"

    assert items[2]["matched_by"] == ["vector"]
    assert items[2]["page_number"] == 3
    assert items[2]["content_type"] == "document"


async def test_search_is_scoped_to_the_project(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    first_project = await create_project(client, "First")
    second_project = await create_project(client, "Second")
    async with session_factory() as session:
        first_document = await create_document(
            session, first_project, "first/notes.md", file_type="markdown"
        )
        await add_chunk(
            session,
            first_document,
            0,
            "shared token only in the first project",
            embedding=vector(1.0),
            content_type="document",
            language=None,
        )
        second_document = await create_document(
            session, second_project, "second/notes.md", file_type="markdown"
        )
        await add_chunk(
            session,
            second_document,
            0,
            "shared token only in the second project",
            embedding=vector(1.0),
            content_type="document",
            language=None,
        )
        await session.commit()

    app.dependency_overrides[get_embedding_client] = lambda: StaticEmbeddingClient(
        vector(1.0)
    )
    response = await client.post(
        f"/api/v1/projects/{first_project}/search",
        json={"query": "shared token"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["items"]
    assert {
        item["project_id"] for item in response.json()["items"]
    } == {first_project}
    assert {
        item["file_path"] for item in response.json()["items"]
    } == {"first/notes.md"}


async def test_keyword_mode_finds_an_exact_identifier(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    project_id = await create_project(client)
    async with session_factory() as session:
        document = await create_document(session, project_id, "src/tax.py")
        await add_chunk(
            session,
            document,
            0,
            "def calculate_tax(amount):\n    return amount * 0.2",
            embedding=vector(0.0, 1.0),
            symbol_name="calculate_tax",
            symbol_type="function",
            start_line=1,
            end_line=2,
        )
        await add_chunk(
            session,
            document,
            1,
            "Prose about tax calculation and reporting.",
            embedding=vector(1.0, 0.0),
            content_type="document",
            language=None,
        )
        await session.commit()

    app.dependency_overrides[get_embedding_client] = lambda: FailingEmbeddingClient()
    response = await client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "calculate_tax", "mode": "keyword"},
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["symbol_name"] == "calculate_tax"
    assert items[0]["matched_by"] == ["keyword"]
    assert items[0]["vector_score"] is None
    assert items[0]["keyword_score"] > 0


@pytest.mark.parametrize(
    ("filters", "expected_path"),
    [
        ({"file_path": "docs/guide.md"}, "docs/guide.md"),
        ({"file_type": "markdown"}, "docs/guide.md"),
        ({"language": "python"}, "backend/app/retrieval/hybrid.py"),
        ({"symbol_type": "class"}, "backend/tests/test_search.py"),
        ({"directory": "backend/app/retrieval"}, "backend/app/retrieval/hybrid.py"),
        ({"document_type": "document"}, "docs/guide.md"),
        (
            {"file_type": "code", "language": "javascript"},
            "backend/tests/test_search.py",
        ),
    ],
)
async def test_metadata_filters(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    filters: dict,
    expected_path: str,
) -> None:
    project_id = await create_project(client)
    async with session_factory() as session:
        code = await create_document(
            session, project_id, "backend/app/retrieval/hybrid.py"
        )
        await add_chunk(
            session,
            code,
            0,
            "shared retrieval token in the hybrid module",
            embedding=vector(1.0),
            symbol_name="reciprocal_rank_fusion",
            symbol_type="function",
        )
        guide = await create_document(
            session, project_id, "docs/guide.md", file_type="markdown"
        )
        await add_chunk(
            session,
            guide,
            0,
            "shared retrieval token in the guide",
            embedding=vector(0.8, 0.2),
            content_type="document",
            language=None,
        )
        test_file = await create_document(
            session, project_id, "backend/tests/test_search.py"
        )
        await add_chunk(
            session,
            test_file,
            0,
            "shared retrieval token in the test file",
            embedding=vector(0.6, 0.4),
            content_type="code",
            language="javascript",
            symbol_name="SearchTests",
            symbol_type="class",
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "shared", "mode": "keyword", "filters": filters},
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items
    assert {item["file_path"] for item in items} == {expected_path}


async def test_empty_project_returns_an_empty_result_set(
    client: AsyncClient,
) -> None:
    project_id = await create_project(client)
    response = await client.post(
        f"/api/v1/projects/{project_id}/search", json={"query": "anything"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_unknown_project_is_not_found(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/projects/{uuid.uuid4()}/search", json={"query": "anything"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   "},
        {"query": "x", "limit": 0},
        {"query": "x", "limit": 51},
        {"query": "x", "mode": "semantic"},
        {"query": "x", "filters": {"project_id": str(uuid.uuid4())}},
    ],
)
async def test_search_request_is_validated(
    client: AsyncClient, payload: dict
) -> None:
    project_id = await create_project(client)
    response = await client.post(
        f"/api/v1/projects/{project_id}/search", json=payload
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_query_vector_width_is_refused_before_sql(
    client: AsyncClient,
) -> None:
    project_id = await create_project(client)
    app.dependency_overrides[get_embedding_client] = lambda: StaticEmbeddingClient(
        [0.0] * 8
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "anything", "mode": "vector"},
    )

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "model_server_error"
    assert "1024" in error["message"]


async def test_misconfigured_embedding_dimension_is_refused(
    client: AsyncClient, app_settings: Settings
) -> None:
    project_id = await create_project(client)
    app.dependency_overrides[get_settings] = lambda: app_settings.model_copy(
        update={"embedding_dimension": 8}
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/search",
        json={"query": "anything", "mode": "vector"},
    )

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "configuration_error"
    assert "1024" in error["message"]


def test_directory_and_file_path_filters_normalise_slashes() -> None:
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        content="content",
        content_type="code",
        metadata_={},
    )

    assert matches_filters(
        chunk, "src/app.py", "code", SearchFilters(directory="src")
    )
    assert not matches_filters(
        chunk, "src2/app.py", "code", SearchFilters(directory="src")
    )
    assert matches_filters(
        chunk,
        "src\\app.py",
        "code",
        SearchFilters(file_path="./src/app.py"),
    )


def _candidate(
    chunk_index: int,
    *,
    vector_score: float | None = None,
    keyword_score: float | None = None,
) -> ChunkCandidate:
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=chunk_index,
        content=f"content {chunk_index}",
        content_type="document",
    )
    return ChunkCandidate(
        chunk=chunk,
        file_path="docs/guide.md",
        filename="guide.md",
        file_type="markdown",
        vector_score=vector_score,
        keyword_score=keyword_score,
    )


def test_rrf_deduplicates_and_keeps_both_component_scores() -> None:
    shared = _candidate(0, vector_score=0.95)
    shared_keyword = ChunkCandidate(
        chunk=shared.chunk,
        file_path=shared.file_path,
        filename=shared.filename,
        file_type=shared.file_type,
        keyword_score=4.0,
    )
    vector_only = _candidate(1, vector_score=0.80)
    keyword_only = _candidate(2, keyword_score=4.0)

    fused = reciprocal_rank_fusion(
        [shared, vector_only], [shared_keyword, keyword_only], limit=10
    )

    assert [result.chunk.chunk_index for result in fused] == [0, 1, 2]
    assert [result.chunk_id for result in fused].count(shared.chunk.id) == 1
    assert fused[0].matched_by == ("vector", "keyword")
    assert fused[0].score == pytest.approx(2.0 / 61.0)
    assert fused[0].vector_score == 0.95
    assert fused[0].keyword_score == 4.0
    assert fused[1].matched_by == ("vector",)
    assert fused[2].matched_by == ("keyword",)
