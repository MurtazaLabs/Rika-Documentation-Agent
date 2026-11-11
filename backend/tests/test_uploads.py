"""Uploads, archive safety, ingestion jobs and chunk storage."""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

import docx
import pymupdf
import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.exceptions import PayloadTooLargeError
from app.database.models import (
    Document,
    DocumentChunk,
    FileVersion,
    IngestionJob,
    ProjectDependency,
    ProjectSymbol,
)
from app.ingestion.archive import extract_zip
from app.ingestion.pipeline import run_ingestion
from app.services import job_service
from tests.conftest import FakeEmbeddingClient


async def create_project(client: AsyncClient, name: str = "Uploads") -> str:
    response = await client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def quiet_queue(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    """Record enqueue calls instead of talking to the broker."""
    queued: list[uuid.UUID] = []

    def _enqueue(job_id: uuid.UUID) -> bool:
        queued.append(job_id)
        return True

    monkeypatch.setattr(job_service, "enqueue_job", _enqueue)
    return queued


def make_zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def make_pdf_bytes(pages: list[str]) -> bytes:
    document = pymupdf.open()
    try:
        for text in pages:
            page = document.new_page()
            page.insert_text((72, 72), text)
        return document.tobytes()
    finally:
        document.close()


def make_pptx_bytes() -> bytes:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Architecture"
    slide.placeholders[1].text = "Ingestion pipeline"
    table = slide.shapes.add_table(
        2, 2, Inches(1), Inches(4), Inches(4), Inches(1)
    ).table
    table.cell(0, 0).text = "Component"
    table.cell(0, 1).text = "Owner"
    table.cell(1, 0).text = "API"
    table.cell(1, 1).text = "Rika"
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def make_xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Users"
    sheet.append(["id", "name"])
    sheet.append([1, "Ada"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_docx_bytes() -> bytes:
    document = docx.Document()
    document.add_heading("Architecture", level=1)
    document.add_paragraph("Body text.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def upload(
    client: AsyncClient, project_id: str, name: str, data: bytes, media: str = "text/plain"
):
    return await client.post(
        f"/api/v1/projects/{project_id}/upload",
        files=[("files", (name, data, media))],
    )


async def test_upload_stores_file_and_queues_job(
    client: AsyncClient, app_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    queued = quiet_queue(monkeypatch)
    project_id = await create_project(client)
    content = b"# Title\n\nBody text here.\n"

    response = await upload(client, project_id, "notes.md", content, "text/markdown")

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    document = item["document"]
    assert item["duplicate"] is False
    assert document["original_path"] == "notes.md"
    assert document["file_type"] == "markdown"
    assert document["status"] == "pending"
    assert document["size"] == len(content)
    assert "stored_path" not in document

    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["status"] == "queued"
    assert body["jobs"][0]["progress"] == 0
    assert queued == [uuid.UUID(body["jobs"][0]["id"])]

    stored = (
        app_settings.storage_root
        / "uploads"
        / project_id
        / document["id"]
        / "notes.md"
    )
    assert stored.is_file()
    assert stored.read_bytes() == content


async def test_unsupported_extension_is_rejected(client: AsyncClient) -> None:
    project_id = await create_project(client)
    response = await upload(client, project_id, "tool.exe", b"MZ\x90\x00binary")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_upload"
    assert ".exe" in response.json()["error"]["message"]

    listing = await client.get(f"/api/v1/projects/{project_id}/documents")
    assert listing.json()["total"] == 0


async def test_empty_and_binary_files_are_rejected(client: AsyncClient) -> None:
    project_id = await create_project(client)

    empty = await upload(client, project_id, "empty.txt", b"")
    assert empty.status_code == 422
    assert "empty" in empty.json()["error"]["message"].lower()

    binary = await upload(client, project_id, "data.txt", b"abc\x00def")
    assert binary.status_code == 422
    assert "binary" in binary.json()["error"]["message"].lower()

    disguised_pdf = await upload(client, project_id, "fake.pdf", b"not a pdf")
    assert disguised_pdf.status_code == 422
    assert "PDF" in disguised_pdf.json()["error"]["message"]


async def test_upload_limit_is_enforced(
    client: AsyncClient, app_settings: Settings
) -> None:
    app_settings.max_upload_mb = 1
    project_id = await create_project(client)

    response = await upload(client, project_id, "big.txt", b"x" * (1024 * 1024 + 10))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    listing = await client.get(f"/api/v1/projects/{project_id}/documents")
    assert listing.json()["total"] == 0


async def test_duplicate_content_is_not_indexed_twice(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    content = b"identical bytes"

    first = await upload(client, project_id, "a.txt", content)
    second = await upload(client, project_id, "copy.txt", content)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["items"][0]["duplicate"] is True
    assert second.json()["jobs"] == []
    assert second.json()["items"][0]["document"]["id"] == first.json()["items"][0]["document"]["id"]

    listing = await client.get(f"/api/v1/projects/{project_id}/documents")
    assert listing.json()["total"] == 1


async def test_changed_file_at_same_path_is_replaced(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)

    first = await upload(client, project_id, "src/app.py", b"print('one')\n")
    document_id = first.json()["items"][0]["document"]["id"]

    second = await upload(client, project_id, "src/app.py", b"print('two')\n")
    assert second.status_code == 201
    item = second.json()["items"][0]
    assert item["duplicate"] is False
    assert item["document"]["id"] == document_id
    assert second.json()["jobs"][0]["job_type"] == "reindex"

    async with session_factory() as session:
        versions = await session.scalar(
            select(func.count())
            .select_from(FileVersion)
            .where(FileVersion.document_id == uuid.UUID(document_id))
        )
        documents = await session.scalar(select(func.count()).select_from(Document))
    assert versions == 2
    assert documents == 1


async def test_folder_upload_keeps_relative_paths(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/upload-folder",
        files=[
            ("files", ("main.py", b"def main(): pass\n", "text/x-python")),
            ("files", ("readme.md", b"# Docs\n", "text/markdown")),
        ],
        data={"paths": ["src/app/main.py", "readme.md"]},
    )

    assert response.status_code == 201, response.text
    paths = sorted(item["document"]["original_path"] for item in response.json()["items"])
    assert paths == ["readme.md", "src/app/main.py"]


async def test_folder_upload_rejects_mismatched_paths(client: AsyncClient) -> None:
    project_id = await create_project(client)
    response = await client.post(
        f"/api/v1/projects/{project_id}/upload-folder",
        files=[("files", ("a.txt", b"hello", "text/plain"))],
        data={"paths": ["a.txt", "b.txt"]},
    )
    assert response.status_code == 422


async def test_path_traversal_is_rejected(client: AsyncClient) -> None:
    project_id = await create_project(client)

    for bad_path in ("../../etc/passwd", "/absolute/file.txt", "C:\\Windows\\win.ini"):
        response = await client.post(
            f"/api/v1/projects/{project_id}/upload-folder",
            files=[("files", ("file.txt", b"hello", "text/plain"))],
            data={"paths": [bad_path]},
        )
        assert response.status_code == 422, bad_path
        assert response.json()["error"]["code"] == "invalid_upload"


async def test_zip_upload_extracts_supported_files_only(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    archive = make_zip(
        {
            "docs/guide.md": b"# Guide\n",
            "src/main.py": b"print('hi')\n",
            "assets/logo.png": b"\x89PNG\r\n",
        }
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/upload-zip",
        files=[("file", ("project.zip", archive, "application/zip"))],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    paths = sorted(item["document"]["original_path"] for item in body["items"])
    assert paths == ["docs/guide.md", "src/main.py"]
    assert body["skipped"] == ["assets/logo.png"]
    assert len(body["jobs"]) == 2


async def test_zip_with_traversal_entry_is_rejected(client: AsyncClient) -> None:
    project_id = await create_project(client)
    archive = make_zip({"../escape.txt": b"nope"})

    response = await client.post(
        f"/api/v1/projects/{project_id}/upload-zip",
        files=[("file", ("evil.zip", archive, "application/zip"))],
    )

    assert response.status_code == 422
    assert "traversal" in response.json()["error"]["message"].lower()


async def test_zip_file_count_limit(
    client: AsyncClient, app_settings: Settings
) -> None:
    app_settings.max_archive_files = 2
    project_id = await create_project(client)
    archive = make_zip({f"f{index}.txt": b"x" for index in range(3)})

    response = await client.post(
        f"/api/v1/projects/{project_id}/upload-zip",
        files=[("file", ("many.zip", archive, "application/zip"))],
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.production",
        "credentials.json",
        "id_rsa",
        "deploy.key",
        "service-account-ci.json",
    ],
)
async def test_credential_files_are_never_indexed(
    client: AsyncClient, name: str
) -> None:
    project_id = await create_project(client)

    response = await upload(client, project_id, name, b"TOKEN=secret-value")

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_upload"
    assert "credentials" in response.json()["error"]["message"].lower()


async def test_environment_template_is_indexable(client: AsyncClient) -> None:
    project_id = await create_project(client)

    response = await upload(client, project_id, ".env.example", b"APP_NAME=Rika\n")

    assert response.status_code == 201, response.text
    assert len(response.json()["items"]) == 1


async def test_zip_bomb_is_refused(tmp_path: Path) -> None:
    archive = make_zip({"bomb.txt": b"\x00" * (12 * 1024 * 1024)})
    zip_path = tmp_path / "bomb.zip"
    zip_path.write_bytes(archive)

    with pytest.raises(PayloadTooLargeError) as caught:
        # A generous size cap, so only the compression ratio can reject it.
        extract_zip(
            zip_path,
            tmp_path / "out",
            max_files=10,
            max_expanded_bytes=50 * 1024 * 1024,
        )

    assert "compression ratio" in str(caught.value).lower()


async def test_non_zip_upload_is_rejected(client: AsyncClient) -> None:
    project_id = await create_project(client)
    response = await client.post(
        f"/api/v1/projects/{project_id}/upload-zip",
        files=[("file", ("not-a.zip", b"plain text", "application/zip"))],
    )
    assert response.status_code == 422
    assert "ZIP" in response.json()["error"]["message"]


async def test_upload_to_unknown_project_is_404(client: AsyncClient) -> None:
    response = await upload(client, str(uuid.uuid4()), "a.txt", b"hello")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_ingestion_indexes_chunks_with_line_ranges(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    text = "\n".join(f"line {number:03d} " + "y" * 40 for number in range(1, 61))
    upload_response = await upload(client, project_id, "long.txt", text.encode())
    job_id = uuid.UUID(upload_response.json()["jobs"][0]["id"])

    async with session_factory() as session:
        result = await run_ingestion(session, job_id, app_settings, embeddings)

    assert result["status"] == "succeeded"
    assert result["chunks"] and result["chunks"] > 1

    async with session_factory() as session:
        job = await session.get(IngestionJob, job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert job.progress == 100
        assert job.attempts == 1
        assert job.started_at is not None and job.completed_at is not None
        assert job.error_message is None

        document = await session.get(Document, job.document_id)
        assert document is not None and document.status == "indexed"

        chunks = (
            await session.scalars(
                select(DocumentChunk).order_by(DocumentChunk.chunk_index)
            )
        ).all()
    assert len(chunks) == result["chunks"]
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 60
    assert all(chunk.content_type == "document" for chunk in chunks)
    assert all(len(chunk.embedding or []) == 1024 for chunk in chunks)
    assert all(chunk.embedding_model == app_settings.embedding_model_name for chunk in chunks)
    assert all(chunk.content.strip() for chunk in chunks)
    # Batches respect EMBEDDING_BATCH_SIZE and cover every chunk exactly once.
    assert len(embeddings.batches) > 1
    assert all(len(batch) <= 4 for batch in embeddings.batches)
    assert sum(len(batch) for batch in embeddings.batches) == len(chunks)
    assert [text for batch in embeddings.batches for text in batch] == [
        chunk.content for chunk in chunks
    ]


async def test_reingestion_replaces_chunks(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "doc.txt", b"one\ntwo\nthree\n")
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])

    async with session_factory() as session:
        await run_ingestion(session, job_id, app_settings, embeddings)
    async with session_factory() as session:
        first = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(response.json()["items"][0]["document"]["id"]))
        )

    async with session_factory() as session:
        await run_ingestion(session, job_id, app_settings, embeddings)
    async with session_factory() as session:
        second = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(response.json()["items"][0]["document"]["id"]))
        )

    assert first == second == 1


async def test_unparseable_document_records_the_failure(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    # Passes the signature check but is not a readable PDF.
    response = await upload(client, project_id, "broken.pdf", b"%PDF-1.4\n garbage")
    assert response.status_code == 201
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])

    async with session_factory() as session:
        result = await run_ingestion(session, job_id, app_settings, embeddings)

    assert result["status"] == "failed"
    assert result["error"]

    async with session_factory() as session:
        job = await session.get(IngestionJob, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.error_message
        document = await session.get(Document, job.document_id)
        assert document is not None and document.status == "failed"
        chunks = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == job.document_id)
        )
    assert chunks == 0


async def test_delete_document_removes_chunks_and_files(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "gone.txt", b"delete me\n")
    document_id = response.json()["items"][0]["document"]["id"]
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])

    async with session_factory() as session:
        await run_ingestion(session, job_id, app_settings, embeddings)

    delete = await client.delete(f"/api/v1/documents/{document_id}")
    assert delete.status_code == 204

    async with session_factory() as session:
        assert await session.get(Document, uuid.UUID(document_id)) is None
        assert await session.get(IngestionJob, job_id) is None
        chunks = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(document_id))
        )
    assert chunks == 0
    assert not (app_settings.storage_root / "uploads" / project_id / document_id).exists()

    missing = await client.delete(f"/api/v1/documents/{document_id}")
    assert missing.status_code == 404


async def test_reindex_endpoint_creates_a_job(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "again.md", b"# Again\n")
    document_id = response.json()["items"][0]["document"]["id"]

    reindex = await client.post(f"/api/v1/documents/{document_id}/reindex")

    assert reindex.status_code == 202
    assert reindex.json()["job_type"] == "reindex"
    assert reindex.json()["status"] == "queued"

    document = await client.get(f"/api/v1/documents/{document_id}")
    assert document.json()["status"] == "pending"

    jobs = await client.get(f"/api/v1/projects/{project_id}/jobs")
    assert jobs.json()["total"] == 2


async def test_job_endpoints_expose_progress_and_retry(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "bad.pdf", b"%PDF-1.4\n garbage")
    job_id = response.json()["jobs"][0]["id"]

    async with session_factory() as session:
        await run_ingestion(session, uuid.UUID(job_id), app_settings, embeddings)

    fetched = await client.get(f"/api/v1/jobs/{job_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "failed"
    assert fetched.json()["error_message"]

    listed = await client.get(f"/api/v1/projects/{project_id}/jobs")
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == job_id

    retried = await client.post(f"/api/v1/jobs/{job_id}/retry")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert retried.json()["error_message"] is None

    conflict = await client.post(f"/api/v1/jobs/{job_id}/retry")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"

    unknown = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert unknown.status_code == 404


async def test_documents_are_project_scoped(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_queue(monkeypatch)
    first = await create_project(client, "First")
    second = await create_project(client, "Second")
    await upload(client, first, "only-here.txt", b"scoped content")

    mine = await client.get(f"/api/v1/projects/{first}/documents")
    theirs = await client.get(f"/api/v1/projects/{second}/documents")
    assert mine.json()["total"] == 1
    assert theirs.json()["total"] == 0


async def test_office_uploads_are_validated_by_container(client: AsyncClient) -> None:
    project_id = await create_project(client)

    broken = await upload(client, project_id, "deck.pptx", b"not a zip")
    assert broken.status_code == 422
    assert "PPTX" in broken.json()["error"]["message"]

    wrong_container = await upload(client, project_id, "deck.pptx", make_docx_bytes())
    assert wrong_container.status_code == 422
    assert "PPTX" in wrong_container.json()["error"]["message"]

    broken_sheet = await upload(client, project_id, "book.xlsx", b"not a zip")
    assert broken_sheet.status_code == 422
    assert "XLSX" in broken_sheet.json()["error"]["message"]


async def test_pptx_ingestion_keeps_slide_metadata(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "deck.pptx", make_pptx_bytes())
    assert response.status_code == 201, response.text
    item = response.json()["items"][0]["document"]
    assert item["file_type"] == "pptx"

    async with session_factory() as session:
        result = await run_ingestion(
            session, uuid.UUID(response.json()["jobs"][0]["id"]), app_settings, embeddings
        )
    assert result["status"] == "succeeded"

    async with session_factory() as session:
        chunks = (
            await session.scalars(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == uuid.UUID(item["id"])
                )
            )
        ).all()

    assert chunks
    assert all(chunk.metadata_["slide_number"] == 1 for chunk in chunks)
    assert all(chunk.page_number is None for chunk in chunks)
    assert chunks[0].metadata_["slides"] == 1
    assert chunks[0].metadata_["tables"] == 1
    assert "Ingestion pipeline" in "\n".join(chunk.content for chunk in chunks)


async def test_xlsx_ingestion_keeps_sheet_metadata(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(client, project_id, "book.xlsx", make_xlsx_bytes())
    assert response.status_code == 201, response.text
    item = response.json()["items"][0]["document"]
    assert item["file_type"] == "xlsx"

    async with session_factory() as session:
        result = await run_ingestion(
            session, uuid.UUID(response.json()["jobs"][0]["id"]), app_settings, embeddings
        )
    assert result["status"] == "succeeded"

    async with session_factory() as session:
        chunks = (
            await session.scalars(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == uuid.UUID(item["id"])
                )
            )
        ).all()

    assert chunks
    assert all(chunk.metadata_["sheet_name"] == "Users" for chunk in chunks)
    assert chunks[0].metadata_["sheet_names"] == ["Users"]
    assert chunks[0].metadata_["rows"] == 2
    assert "1 | Ada" in "\n".join(chunk.content for chunk in chunks)


async def test_pdf_ingestion_stores_page_numbers(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    project_id = await create_project(client)
    response = await upload(
        client,
        project_id,
        "manual.pdf",
        make_pdf_bytes(["First page architecture", "Second page parsing"]),
    )
    assert response.status_code == 201, response.text
    item = response.json()["items"][0]["document"]

    async with session_factory() as session:
        result = await run_ingestion(
            session, uuid.UUID(response.json()["jobs"][0]["id"]), app_settings, embeddings
        )
    assert result["status"] == "succeeded"

    async with session_factory() as session:
        chunks = (
            await session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == uuid.UUID(item["id"]))
                .order_by(DocumentChunk.chunk_index)
            )
        ).all()

    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert all("[page" not in chunk.content.lower() for chunk in chunks)
    assert chunks[0].metadata_["pages"] == 2
    assert chunks[1].content.strip().startswith("Second page")


CODE_SOURCE = '''import os

from app.core import config


class Worker:
    def run(self):
        value = os.getcwd()
        return value

    def stop(self):
        return True


def main():
    worker = Worker()
    return worker.run()
'''


async def test_code_ingestion_persists_symbols_and_dependencies(
    client: AsyncClient,
    app_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: FakeEmbeddingClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_queue(monkeypatch)
    app_settings.chunk_size_chars = 100
    app_settings.chunk_overlap_chars = 20
    project_id = await create_project(client)
    response = await upload(client, project_id, "worker.py", CODE_SOURCE.encode())
    assert response.status_code == 201, response.text
    item = response.json()["items"][0]["document"]
    job_id = uuid.UUID(response.json()["jobs"][0]["id"])

    async with session_factory() as session:
        result = await run_ingestion(session, job_id, app_settings, embeddings)
    assert result["status"] == "succeeded"

    async with session_factory() as session:
        chunks = (
            await session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == uuid.UUID(item["id"]))
                .order_by(DocumentChunk.chunk_index)
            )
        ).all()
        symbols = (await session.scalars(select(ProjectSymbol))).all()
        dependencies = (await session.scalars(select(ProjectDependency))).all()

    assert all(chunk.content_type == "code" for chunk in chunks)
    assert all(chunk.language == "python" for chunk in chunks)
    assert "Worker" in {chunk.symbol_name for chunk in chunks}
    run_chunks = [chunk for chunk in chunks if chunk.symbol_name == "run"]
    assert run_chunks
    assert run_chunks[0].metadata_["symbol_type"] == "method"
    assert run_chunks[0].metadata_["parent_symbol"] == "Worker"
    assert run_chunks[0].metadata_["file_path"] == "worker.py"

    qualified = {symbol.qualified_name for symbol in symbols}
    assert {"Worker", "Worker.run", "Worker.stop", "main"} <= qualified
    assert all(symbol.metadata_["file_path"] == "worker.py" for symbol in symbols)
    assert {dependency.target_reference for dependency in dependencies} == {
        "os",
        "app.core",
    }

    # Re-indexing replaces rows instead of duplicating them.
    async with session_factory() as session:
        await run_ingestion(session, job_id, app_settings, embeddings)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ProjectSymbol)) == len(
            symbols
        )
        assert await session.scalar(
            select(func.count()).select_from(ProjectDependency)
        ) == len(dependencies)
        assert await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(item["id"]))
        ) == len(chunks)

