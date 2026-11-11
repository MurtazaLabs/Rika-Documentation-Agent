"""Chat answers can cite the derived project intelligence reports."""

from __future__ import annotations

import hashlib
import json
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.constants import EMBEDDING_VECTOR_DIMENSION
from app.database.models import Document, DocumentChunk
from tests.conftest import FakeChatClient, FakeEmbeddingClient

EMBEDDING = [0.5] * EMBEDDING_VECTOR_DIMENSION


async def create_project(client: AsyncClient, name: str = "Intelligence") -> str:
    response = await client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def add_file(
    session_factory: async_sessionmaker[AsyncSession],
    project_id: str,
    path: str,
    content: str,
) -> None:
    """One indexed code file, enough for the reports to have something to say."""
    digest = hashlib.sha256(f"{project_id}:{path}".encode()).hexdigest()
    async with session_factory() as session:
        document = Document(
            project_id=uuid.UUID(project_id),
            original_path=path,
            stored_path=f"{project_id}/{digest}",
            filename=path.rsplit("/", 1)[-1],
            file_type="code",
            content_hash=digest,
            size=len(content),
            status="indexed",
        )
        session.add(document)
        await session.flush()
        session.add(
            DocumentChunk(
                project_id=uuid.UUID(project_id),
                document_id=document.id,
                chunk_index=0,
                content=content,
                embedding=EMBEDDING,
                embedding_model=FakeEmbeddingClient.model_name,
                content_type="code",
                language="python",
                start_line=1,
                end_line=max(1, content.count("\n") + 1),
                metadata_={"file_path": path, "file_type": "code"},
            )
        )
        await session.commit()


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        name = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        assert name, block
        events.append((name, json.loads(data)))
    return events


async def test_chat_cites_derived_intelligence_items(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChatClient,
) -> None:
    project_id = await create_project(client)
    await add_file(
        session_factory,
        project_id,
        "backend/app/retrieval/hybrid.py",
        "def reciprocal_rank_fusion():\n    return []\n",
    )
    chat.response = (
        "Fusion happens in the retrieval module [S1]. "
        "The project is organised in layers [I1]."
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={"message": "Which layers does this project have?"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grounded"] is True
    assert [item["marker"] for item in body["intelligence"]] == ["I1"]
    assert body["intelligence"][0]["kind"] == "layer"
    # Markers are prompt wiring: the prose keeps the citation-free sentence.
    assert body["answer"] == (
        "Fusion happens in the retrieval module [S1]. "
        "The project is organised in layers."
    )

    prompt = chat.calls[0]["messages"][-1]["content"]
    assert "<project_intelligence>" in prompt
    assert "[I1] (kind=layer)" in prompt
    assert prompt.index("<retrieved_context>") < prompt.index(
        "<project_intelligence>"
    )


async def test_chat_answers_from_intelligence_without_retrieved_chunks(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChatClient,
) -> None:
    project_id = await create_project(client)
    await add_file(
        session_factory,
        project_id,
        "backend/app/retrieval/hybrid.py",
        "def reciprocal_rank_fusion():\n    return []\n",
    )
    chat.response = "This project keeps retrieval separate from storage [I1]."

    response = await client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={
            "message": "How is this project structured?",
            # No chunk can match this filter, but the derived report ignores it.
            "filters": {"file_path": "does/not/exist.py"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["retrieved_chunks"] == 0
    assert body["citations"] == []
    assert body["intelligence"][0]["marker"] == "I1"
    assert body["grounded"] is True
    assert "insufficient_evidence" not in body["warnings"]
    assert chat.calls


async def test_chat_drops_invented_intelligence_markers(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChatClient,
) -> None:
    project_id = await create_project(client)
    await add_file(
        session_factory,
        project_id,
        "backend/app/retrieval/hybrid.py",
        "def reciprocal_rank_fusion():\n    return []\n",
    )
    chat.response = "The layers are indexed [I99]."

    response = await client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={"message": "Which layers are indexed?"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "The layers are indexed."
    assert body["intelligence"] == []
    assert "invalid_intelligence_markers_removed" in body["warnings"]
    assert body["grounded"] is False


async def test_streamed_answer_carries_intelligence(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChatClient,
) -> None:
    project_id = await create_project(client)
    await add_file(
        session_factory,
        project_id,
        "backend/app/retrieval/hybrid.py",
        "def reciprocal_rank_fusion():\n    return []\n",
    )
    chat.stream_chunks = ["Layers are indexed [I1]."]

    async with client.stream(
        "POST",
        f"/api/v1/projects/{project_id}/chat",
        json={"message": "Which layers are indexed?", "stream": True},
    ) as response:
        assert response.status_code == 200, response.text
        body = await response.aread()

    events = parse_sse(body.decode())
    assert [name for name, _ in events] == ["start", "token", "citations", "done"]
    done = events[-1][1]
    assert done["answer"] == "Layers are indexed."
    assert done["intelligence"][0]["marker"] == "I1"
    assert done["grounded"] is True
