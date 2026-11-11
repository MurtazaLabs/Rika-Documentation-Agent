"""Upload staging, validation and document registration.

Bytes are written to ``storage/temp`` while being hashed, validated, and only
then moved under ``storage/uploads/<project>/<document>`` when the database row
is created. Validation is all-or-nothing per request: one rejected file leaves
no rows and no leftover files behind.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import InvalidUploadError, PayloadTooLargeError
from app.database.models import Document, FileVersion, IngestionJob
from app.database.models.enums import DocumentStatus, JobStatus, JobType
from app.ingestion.archive import extract_zip
from app.ingestion.formats import (
    FileFormat,
    format_for,
    is_secret_path,
    supported_extensions,
)
from app.ingestion.paths import filename_of, safe_relative_path
from app.services import project_service

READ_BLOCK = 1024 * 1024
BINARY_SNIFF_BYTES = 8192


@dataclass(slots=True)
class StagedUpload:
    """A validated file waiting for its document row."""

    original_path: str
    temp_path: Path
    format: FileFormat
    size: int
    content_hash: str

    @property
    def filename(self) -> str:
        return filename_of(self.original_path)


@dataclass(slots=True)
class UploadOutcome:
    documents: list[Document]
    jobs: list[IngestionJob]
    duplicates: list[Document] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


async def ingest_uploads(
    session: AsyncSession,
    settings: Settings,
    project_id: uuid.UUID,
    uploads: list[tuple[UploadFile, str]],
) -> UploadOutcome:
    """Stage every upload, then register the ones that are valid."""
    await project_service.get_project(session, project_id)  # 404 before any I/O

    staged: list[StagedUpload] = []
    try:
        for upload, raw_path in uploads:
            staged.append(await stage_upload(settings, upload, raw_path))
    except Exception:
        for item in staged:
            item.temp_path.unlink(missing_ok=True)
        raise

    try:
        created = await _register_staged_batch(session, settings, project_id, staged)
    except Exception:
        for item in staged:
            item.temp_path.unlink(missing_ok=True)
        raise

    outcome = UploadOutcome(documents=[], jobs=[])
    for document, job, duplicate in created:
        if duplicate:
            outcome.duplicates.append(document)
            continue
        outcome.documents.append(document)
        if job is not None:
            outcome.jobs.append(job)
    return outcome


async def ingest_archive(
    session: AsyncSession,
    settings: Settings,
    project_id: uuid.UUID,
    upload: UploadFile,
) -> UploadOutcome:
    """Validate, extract and register every supported file in a ZIP archive."""
    await project_service.get_project(session, project_id)

    archive_path = await _spool_upload(settings, upload, "archive.zip")
    staging_dir = settings.temp_root / f"extract-{uuid.uuid4()}"
    staging_dir.mkdir(parents=True, exist_ok=True)
    try:
        entries = extract_zip(
            archive_path,
            staging_dir,
            max_files=settings.max_archive_files,
            max_expanded_bytes=settings.archive_expanded_limit_bytes,
        )
        skipped = [
            entry.relative_path
            for entry in entries
            if format_for(entry.relative_path) is None
        ]
        supported = [entry for entry in entries if format_for(entry.relative_path)]
        if not supported:
            raise InvalidUploadError(
                "The archive contains no supported files. Supported extensions: "
                + ", ".join(supported_extensions())
            )

        staged: list[StagedUpload] = []
        try:
            for entry in supported:
                staged.append(
                    await stage_local_file(
                        settings,
                        staging_dir / entry.relative_path,
                        entry.relative_path,
                    )
                )
        except Exception:
            for item in staged:
                item.temp_path.unlink(missing_ok=True)
            raise

        try:
            created = await _register_staged_batch(session, settings, project_id, staged)
        except Exception:
            for item in staged:
                item.temp_path.unlink(missing_ok=True)
            raise
        outcome = UploadOutcome(documents=[], jobs=[], skipped=skipped)
        for document, job, duplicate in created:
            if duplicate:
                outcome.duplicates.append(document)
                continue
            outcome.documents.append(document)
            if job is not None:
                outcome.jobs.append(job)
        return outcome
    finally:
        archive_path.unlink(missing_ok=True)
        shutil.rmtree(staging_dir, ignore_errors=True)


async def stage_upload(
    settings: Settings, upload: UploadFile, raw_path: str
) -> StagedUpload:
    """Stream one ``UploadFile`` to temp storage, validating as it goes."""
    original_path = safe_relative_path(raw_path)
    format_ = _require_supported(original_path)
    limit = settings.upload_limit_bytes

    temp_path = settings.temp_root / f"upload-{uuid.uuid4()}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    size = 0
    try:
        with temp_path.open("wb") as destination:
            while True:
                block = await upload.read(READ_BLOCK)
                if not block:
                    break
                size += len(block)
                if size > limit:
                    raise PayloadTooLargeError(
                        f"{original_path} exceeds the {settings.max_upload_mb} MB limit"
                    )
                hasher.update(block)
                destination.write(block)
        _validate_contents(temp_path, original_path, format_, size)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return StagedUpload(
        original_path=original_path,
        temp_path=temp_path,
        format=format_,
        size=size,
        content_hash=hasher.hexdigest(),
    )


async def stage_local_file(
    settings: Settings, source_path: Path, raw_path: str
) -> StagedUpload:
    """Stage a file that is already on disk (an extracted archive entry)."""
    original_path = safe_relative_path(raw_path)
    format_ = _require_supported(original_path)

    temp_path = settings.temp_root / f"upload-{uuid.uuid4()}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    size = 0
    try:
        with source_path.open("rb") as source, temp_path.open("wb") as destination:
            while True:
                block = source.read(READ_BLOCK)
                if not block:
                    break
                size += len(block)
                if size > settings.upload_limit_bytes:
                    raise PayloadTooLargeError(
                        f"{original_path} exceeds the {settings.max_upload_mb} MB limit"
                    )
                hasher.update(block)
                destination.write(block)
        _validate_contents(temp_path, original_path, format_, size)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return StagedUpload(
        original_path=original_path,
        temp_path=temp_path,
        format=format_,
        size=size,
        content_hash=hasher.hexdigest(),
    )


async def _spool_upload(settings: Settings, upload: UploadFile, name: str) -> Path:
    """Write an uploaded archive to temp storage, enforcing the size limit."""
    path = settings.temp_root / f"{uuid.uuid4()}-{name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with path.open("wb") as destination:
            while True:
                block = await upload.read(READ_BLOCK)
                if not block:
                    break
                size += len(block)
                if size > settings.upload_limit_bytes:
                    raise PayloadTooLargeError(
                        f"The archive exceeds the {settings.max_upload_mb} MB limit"
                    )
                destination.write(block)
        if size == 0:
            raise InvalidUploadError("The uploaded archive is empty")
        if not zipfile.is_zipfile(path):
            raise InvalidUploadError("The uploaded file is not a valid ZIP archive")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


async def _register_staged_batch(
    session: AsyncSession,
    settings: Settings,
    project_id: uuid.UUID,
    staged: list[StagedUpload],
) -> list[tuple[Document, IngestionJob | None, bool]]:
    """Register a request atomically and clean filesystem moves on rollback."""
    # get_project() may have opened an implicit read transaction.
    await session.commit()
    moved_paths: list[Path] = []
    try:
        async with session.begin():
            created = []
            for item in staged:
                created.append(
                    await register_document(
                        session, settings, project_id, item, moved_paths=moved_paths
                    )
                )
        return created
    except Exception:
        for path in moved_paths:
            path.unlink(missing_ok=True)
        raise


async def register_document(
    session: AsyncSession,
    settings: Settings,
    project_id: uuid.UUID,
    staged: StagedUpload,
    *,
    moved_paths: list[Path] | None = None,
) -> tuple[Document, IngestionJob | None, bool]:
    """Register one staged file inside the caller's transaction."""
    moved_paths = moved_paths if moved_paths is not None else []

    # Path identity takes precedence over content deduplication. If a path
    # already exists, an upload with changed bytes must update that document,
    # even when those bytes happen to exist at another path in the project.
    same_path = await session.scalar(
        select(Document).where(
            Document.project_id == project_id,
            Document.original_path == staged.original_path,
        )
    )
    if same_path is not None:
        if same_path.content_hash == staged.content_hash:
            staged.temp_path.unlink(missing_ok=True)
            return same_path, None, True
        document = await _replace_contents(
            session, settings, same_path, staged, moved_paths=moved_paths
        )
        job = IngestionJob(
            project_id=project_id,
            document_id=document.id,
            job_type=JobType.REINDEX.value,
            status=JobStatus.QUEUED.value,
        )
        session.add(job)
        await session.flush()
        return document, job, False

    existing_hash = await session.scalar(
        select(Document).where(
            Document.project_id == project_id,
            Document.content_hash == staged.content_hash,
        )
    )
    if existing_hash is not None:
        staged.temp_path.unlink(missing_ok=True)
        return existing_hash, None, True

    document_id = uuid.uuid4()
    stored_relative = _stored_relative(project_id, document_id, staged.filename)
    destination = settings.storage_root / stored_relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staged.temp_path), destination)
    moved_paths.append(destination)

    document = Document(
        id=document_id,
        project_id=project_id,
        original_path=staged.original_path,
        stored_path=stored_relative.as_posix(),
        filename=staged.filename,
        file_type=staged.format.file_type,
        content_hash=staged.content_hash,
        size=staged.size,
        status=DocumentStatus.PENDING.value,
    )
    session.add(document)
    session.add(
        FileVersion(
            document_id=document_id,
            content_hash=staged.content_hash,
            storage_path=stored_relative.as_posix(),
        )
    )
    job = IngestionJob(
        project_id=project_id,
        document_id=document_id,
        job_type=JobType.INGEST.value,
        status=JobStatus.QUEUED.value,
    )
    session.add(job)
    await session.flush()
    return document, job, False


async def _replace_contents(
    session: AsyncSession,
    settings: Settings,
    document: Document,
    staged: StagedUpload,
    *,
    moved_paths: list[Path],
) -> Document:
    """Create an immutable new file version and point the document at it."""
    version_relative = (
        Path("uploads")
        / str(document.project_id)
        / str(document.id)
        / "versions"
        / str(uuid.uuid4())
        / staged.filename
    )
    destination = settings.storage_root / version_relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staged.temp_path), destination)
    moved_paths.append(destination)

    document.stored_path = version_relative.as_posix()
    document.content_hash = staged.content_hash
    document.size = staged.size
    document.filename = staged.filename
    document.file_type = staged.format.file_type
    document.status = DocumentStatus.PENDING.value
    session.add(
        FileVersion(
            document_id=document.id,
            content_hash=staged.content_hash,
            storage_path=version_relative.as_posix(),
        )
    )
    await session.flush()
    return document


def _require_supported(original_path: str) -> FileFormat:
    if is_secret_path(original_path):
        raise InvalidUploadError(
            f"{original_path} is a credentials file and is never indexed. "
            "Upload an environment template such as .env.example instead."
        )
    format_ = format_for(original_path)
    if format_ is None:
        extension = Path(original_path).suffix.lower() or "(none)"
        raise InvalidUploadError(
            f"Unsupported file extension {extension}. Supported: "
            + ", ".join(supported_extensions())
        )
    return format_


def _validate_contents(
    temp_path: Path, original_path: str, format_: FileFormat, size: int
) -> None:
    """Cheap structural checks so a mislabelled file fails before indexing."""
    if size == 0:
        raise InvalidUploadError(f"{original_path} is empty")

    # Closed before any move: Windows keeps an open handle locked.
    with temp_path.open("rb") as handle:
        head = handle.read(BINARY_SNIFF_BYTES)
    if format_.file_type == "pdf":
        if not head.startswith(b"%PDF-"):
            raise InvalidUploadError(f"{original_path} is not a PDF file")
        return
    if format_.file_type in {"docx", "pptx", "xlsx"}:
        label = format_.file_type.upper()
        expected_prefix = {
            "docx": "word/",
            "pptx": "ppt/",
            "xlsx": "xl/",
        }[format_.file_type]
        if not head.startswith(b"PK\x03\x04"):
            raise InvalidUploadError(f"{original_path} is not a {label} file")
        try:
            with zipfile.ZipFile(temp_path) as archive:
                if not any(
                    name.startswith(expected_prefix) for name in archive.namelist()
                ):
                    raise InvalidUploadError(
                        f"{original_path} is a ZIP file, not a {label} document"
                    )
        except zipfile.BadZipFile as error:
            raise InvalidUploadError(f"{original_path} is not a {label} file") from error
        return
    if b"\x00" in head:
        raise InvalidUploadError(
            f"{original_path} appears to be binary; only text formats are supported"
        )


def _stored_relative(
    project_id: uuid.UUID, document_id: uuid.UUID, filename: str
) -> Path:
    return Path("uploads") / str(project_id) / str(document_id) / filename
