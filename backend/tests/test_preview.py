"""Document preview: stored text, chunk fallback, isolation and safety."""

from __future__ import annotations

import hashlib
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.database.models import Document, DocumentChunk


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", json={"name": "Preview"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _add_document(
    session_factory: async_sessionmaker[AsyncSession],
    project_id: str,
    *,
    original_path: str,
    stored_path: str,
    file_type: str,
) -> uuid.UUID:
    async with session_factory() as session:
        document = Document(
            project_id=uuid.UUID(project_id),
            original_path=original_path,
            stored_path=stored_path,
            filename=original_path.rsplit("/", 1)[-1],
            file_type=file_type,
            content_hash=hashlib.sha256(original_path.encode()).hexdigest(),
            size=64,
            status="indexed",
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def test_preview_reads_text_and_reports_lines(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    app_settings: Settings,
) -> None:
    project_id = await _create_project(client)
    stored_path = f"uploads/{project_id}/{uuid.uuid4()}/app.py"
    path = app_settings.storage_root / stored_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def run():\n    return 42\n", encoding="utf-8")
    document_id = await _add_document(
        session_factory,
        project_id,
        original_path="backend/app.py",
        stored_path=stored_path,
        file_type="code",
    )

    response = await client.get(
        f"/api/v1/documents/{document_id}/preview",
        params={"project_id": project_id},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "file"
    assert body["language"] == "python"
    assert body["content"] == "def run():\n    return 42\n"
    assert body["line_count"] == 2
    assert body["truncated"] is False


async def test_preview_falls_back_to_chunks_for_parsed_formats(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    app_settings: Settings,
) -> None:
    project_id = await _create_project(client)
    document_id = await _add_document(
        session_factory,
        project_id,
        original_path="docs/manual.pdf",
        stored_path=f"uploads/{project_id}/{uuid.uuid4()}/manual.pdf",
        file_type="pdf",
    )
    async with session_factory() as session:
        session.add_all(
            [
                DocumentChunk(
                    project_id=uuid.UUID(project_id),
                    document_id=document_id,
                    chunk_index=0,
                    content="First page body.",
                    content_type="document",
                    page_number=1,
                ),
                DocumentChunk(
                    project_id=uuid.UUID(project_id),
                    document_id=document_id,
                    chunk_index=1,
                    content="Second page body.",
                    content_type="document",
                    page_number=2,
                ),
            ]
        )
        await session.commit()

    response = await client.get(f"/api/v1/documents/{document_id}/preview")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "chunks"
    assert "[page 1]" in body["content"]
    assert "First page body." in body["content"]
    assert "[page 2]" in body["content"]
    assert body["line_count"] is None


async def test_preview_is_project_scoped_and_never_reads_outside_storage(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    app_settings: Settings,
) -> None:
    project_a = await _create_project(client)
    project_b = await _create_project(client)
    outside = app_settings.storage_root.parent / "outside.txt"
    outside.write_text("TOP SECRET", encoding="utf-8")
    document_id = await _add_document(
        session_factory,
        project_a,
        original_path="outside.txt",
        stored_path="../outside.txt",
        file_type="text",
    )

    wrong_project = await client.get(
        f"/api/v1/documents/{document_id}/preview",
        params={"project_id": project_b},
    )
    assert wrong_project.status_code == 404

    response = await client.get(f"/api/v1/documents/{document_id}/preview")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "none"
    assert "TOP SECRET" not in body["content"]


async def test_preview_unknown_document(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/preview")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
