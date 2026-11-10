"""The ingestion pipeline behind :func:`app.workers.tasks.ingest_document`.

Runs in the worker: parse → chunk → embed → store chunks → mark indexed.
Progress is committed at each step so the jobs API can show movement while a
large file is being processed, and every failure is recorded on the job and the
document instead of being swallowed.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.code_intelligence import CodeAnalysis, analyze_code
from app.code_intelligence.chunking import chunk_code
from app.config import Settings
from app.core.constants import EMBEDDING_VECTOR_DIMENSION
from app.database.models import (
    Document,
    DocumentChunk,
    IngestionJob,
    ProjectDependency,
    ProjectSymbol,
)
from app.database.models.enums import ContentType, DocumentStatus, JobStatus
from app.ingestion.chunking import ChunkDraft, chunk_segments, chunk_text
from app.ingestion.embedding import EmbeddingError, embed_texts
from app.ingestion.formats import format_for
from app.ingestion.parsers import ParsedContent, ParsingError, parse_file
from app.llm.llama_client import ModelServerClient

logger = logging.getLogger("rika.ingestion")

MAX_ERROR_CHARS = 2000


async def run_ingestion(
    session: AsyncSession,
    job_id: uuid.UUID,
    settings: Settings,
    embedding_client: ModelServerClient,
) -> dict[str, Any]:
    """Process one ingestion job and return a small result summary."""
    job = await session.get(IngestionJob, job_id)
    if job is None:
        logger.warning("ingestion job %s no longer exists", job_id)
        return {"job_id": str(job_id), "status": "missing"}

    document = (
        await session.get(Document, job.document_id) if job.document_id else None
    )
    # Held separately: a rollback expires the ORM instances, and touching an
    # expired attribute would trigger blocking I/O inside the event loop.
    document_id = document.id if document is not None else None
    if document is None:
        await _fail(
            session, job_id, None, "The job has no document (it was deleted?)", None
        )
        return {"job_id": str(job_id), "status": JobStatus.FAILED.value}

    job.status = JobStatus.RUNNING.value
    job.started_at = _now()
    job.attempts += 1
    job.progress = 5
    job.error_message = None
    document.status = DocumentStatus.PROCESSING.value
    await session.commit()

    try:
        chunks = await _index_document(
            session, job, document, settings, embedding_client
        )
    except Exception as error:  # noqa: BLE001 - recorded, not swallowed
        logger.exception("ingestion failed for document %s", document_id)
        await session.rollback()
        message = (
            str(error)
            if isinstance(error, (ParsingError, EmbeddingError))
            else f"{type(error).__name__}: {error}"
        )
        await _fail(
            session, job_id, document_id, message, getattr(error, "details", None)
        )
        return {
            "job_id": str(job_id),
            "document_id": str(document_id),
            "status": JobStatus.FAILED.value,
            "error": message[:MAX_ERROR_CHARS],
        }

    job.status = JobStatus.SUCCEEDED.value
    job.progress = 100
    job.completed_at = _now()
    document.status = DocumentStatus.INDEXED.value
    await session.commit()
    return {
        "job_id": str(job_id),
        "document_id": str(document_id),
        "status": JobStatus.SUCCEEDED.value,
        "chunks": chunks,
    }


async def _index_document(
    session: AsyncSession,
    job: IngestionJob,
    document: Document,
    settings: Settings,
    embedding_client: ModelServerClient,
) -> int:
    path = settings.storage_root / document.stored_path
    if not path.is_file():
        raise ParsingError(f"The stored file is missing: {document.stored_path}")

    format_ = format_for(document.original_path or document.filename)
    if format_ is None:
        raise ParsingError(f"No parser for {document.original_path}")

    parsed = await run_in_threadpool(parse_file, path, format_)
    job.progress = 30
    await session.commit()

    analysis: CodeAnalysis | None = None
    if format_.content_type == ContentType.CODE:
        analysis = await run_in_threadpool(
            analyze_code,
            format_.language,
            parsed.text,
            document.original_path or document.filename,
        )
        job.progress = 45
        await session.commit()

    if analysis is not None:
        drafts = await run_in_threadpool(
            chunk_code,
            parsed.text,
            analysis,
            max_chars=settings.chunk_size_chars,
            overlap_chars=settings.chunk_overlap_chars,
        )
    else:
        drafts = await run_in_threadpool(_document_drafts, parsed, settings)
    if not drafts:
        raise ParsingError("No text content was extracted from the file")
    job.progress = 55
    await session.commit()

    # Embedding runs before anything is written, so a model-server failure
    # leaves the previous chunks of this document intact.
    vectors = await _embed_drafts(session, job, drafts, settings, embedding_client)

    # Re-indexing replaces the previous chunks/symbols/dependencies rather than
    # appending to them. This happens only after embedding succeeded.
    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
    )
    await session.execute(
        delete(ProjectSymbol).where(ProjectSymbol.document_id == document.id)
    )
    await session.execute(
        delete(ProjectDependency).where(
            ProjectDependency.source_document_id == document.id
        )
    )

    chunk_metadata = _document_metadata(parsed, document, analysis)
    for draft, vector in zip(drafts, vectors, strict=True):
        metadata = dict(chunk_metadata)
        metadata.update(draft.metadata)
        metadata["file_path"] = document.original_path or document.filename
        metadata["content_hash"] = document.content_hash
        page_number = _positive_int(metadata.get("page_number"))
        session.add(
            DocumentChunk(
                project_id=document.project_id,
                document_id=document.id,
                chunk_index=draft.index,
                content=draft.text,
                embedding=vector,
                embedding_model=settings.embedding_model_name,
                content_type=format_.content_type.value,
                language=format_.language,
                symbol_name=_optional_str(draft.symbol_name, 255),
                start_line=draft.start_line,
                end_line=draft.end_line,
                page_number=page_number,
                metadata_=metadata,
            )
        )

    if analysis is not None:
        _add_code_rows(session, document, format_.language, analysis)

    job.progress = 95
    await session.flush()
    return len(drafts)


def _document_drafts(parsed: ParsedContent, settings: Settings) -> list[ChunkDraft]:
    """Chunk parsed segments when structure exists, otherwise the flat text."""
    if parsed.segments:
        drafts = chunk_segments(
            parsed.segments,
            max_chars=settings.chunk_size_chars,
            overlap_chars=settings.chunk_overlap_chars,
        )
        if drafts:
            return drafts
    return chunk_text(
        parsed.text,
        max_chars=settings.chunk_size_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )


def _document_metadata(
    parsed: ParsedContent,
    document: Document,
    analysis: CodeAnalysis | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "file_path": document.original_path or document.filename,
        "content_hash": document.content_hash,
        "file_type": document.file_type,
    }
    for key in (
        "language",
        "pages",
        "slides",
        "sheets",
        "sheet_names",
        "headings",
        "sections",
        "paragraphs",
        "tables",
        "table_rows",
        "rows",
        "columns",
        "json_root",
    ):
        value = parsed.metadata.get(key)
        if value not in (None, "", []):
            metadata[key] = value
    warnings = list(parsed.warnings)
    if analysis is not None:
        warnings.extend(analysis.warnings)
        if analysis.grammar:
            metadata["grammar"] = analysis.grammar
    if warnings:
        metadata["warnings"] = warnings
    return metadata


def _add_code_rows(
    session: AsyncSession,
    document: Document,
    language: str | None,
    analysis: CodeAnalysis,
) -> None:
    file_path = document.original_path or document.filename
    for symbol in analysis.symbols:
        session.add(
            ProjectSymbol(
                project_id=document.project_id,
                document_id=document.id,
                symbol_type=_optional_str(symbol.symbol_type, 32) or "symbol",
                symbol_name=_optional_str(symbol.name, 255) or "(anonymous)",
                qualified_name=_optional_str(symbol.qualified_name, 512),
                start_line=max(symbol.start_line, 1),
                end_line=max(symbol.end_line, symbol.start_line, 1),
                metadata_={
                    **symbol.metadata,
                    "file_path": file_path,
                    "content_hash": document.content_hash,
                    "language": language,
                },
            )
        )
    for dependency in analysis.dependencies:
        target = _optional_str(dependency.target_reference, 512)
        if not target:
            continue
        session.add(
            ProjectDependency(
                project_id=document.project_id,
                source_document_id=document.id,
                target_reference=target,
                dependency_type=_optional_str(dependency.dependency_type, 32)
                or "import",
            )
        )


def _optional_str(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned[:limit] if cleaned else None


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


async def _embed_drafts(
    session: AsyncSession,
    job: IngestionJob,
    drafts: list[ChunkDraft],
    settings: Settings,
    embedding_client: ModelServerClient,
) -> list[list[float]]:
    """Embed every chunk, refusing a model that cannot fill the column."""
    dimension = settings.embedding_dimension
    if dimension is None:
        raise EmbeddingError(
            "EMBEDDING_DIMENSION is not set; run 'python -m app.cli check-models' "
            "and put the reported dimension in .env"
        )
    if dimension != EMBEDDING_VECTOR_DIMENSION:
        raise EmbeddingError(
            f"EMBEDDING_DIMENSION={dimension} does not match the "
            f"{EMBEDDING_VECTOR_DIMENSION}-dimension vector column; "
            "reindexing needs a migration for the new model"
        )

    async def report(done: int, total: int) -> None:
        # 55 -> 90 while the model works through the file.
        job.progress = 55 + int(35 * done / total)
        await session.commit()

    return await embed_texts(
        embedding_client,
        [draft.text for draft in drafts],
        dimension=dimension,
        batch_size=settings.embedding_batch_size,
        on_progress=report,
    )


async def _fail(
    session: AsyncSession,
    job_id: uuid.UUID,
    document_id: uuid.UUID | None,
    message: str,
    details: dict[str, Any] | None,
) -> None:
    """Record a failure on fresh rows (the session may have been rolled back)."""
    job = await session.get(IngestionJob, job_id)
    if job is not None:
        job.status = JobStatus.FAILED.value
        job.error_message = message[:MAX_ERROR_CHARS]
        job.completed_at = _now()
    if document_id is not None:
        document = await session.get(Document, document_id)
        if document is not None:
            document.status = DocumentStatus.FAILED.value
    if details:
        logger.debug("ingestion failure details: %s", details)
    await session.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = ["run_ingestion"]
