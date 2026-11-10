"""Celery tasks.

``rika.ping`` is the connectivity probe used by ``python -m app.cli
check-worker``. ``rika.ingest_document`` parses, chunks, embeds and indexes an
uploaded file inside the worker, so the API never blocks on file processing.
"""

from __future__ import annotations

import asyncio
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(name="rika.ingest_document")
def ingest_document(job_id: str) -> dict[str, Any]:
    """Process one ingestion job end to end (parse → chunk → embed → store)."""
    return asyncio.run(_run_ingestion(uuid.UUID(job_id)))


async def _run_ingestion(job_id: uuid.UUID) -> dict[str, Any]:
    from app.config import get_settings
    from app.database.session import create_engine, create_session_factory
    from app.ingestion.pipeline import run_ingestion
    from app.llm.llama_client import ModelServerClient

    settings = get_settings()
    # The worker owns its engine: no request context, and a long-running
    # process must not share a loop-bound pool with the API.
    engine = create_engine(settings)
    embedding_client = ModelServerClient(
        settings.embedding_base_url,
        settings.embedding_model_name,
        timeout=settings.embedding_timeout,
    )
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            return await run_ingestion(session, job_id, settings, embedding_client)
    finally:
        await embedding_client.aclose()
        await engine.dispose()


@celery_app.task(name="rika.ping")
def ping(payload: str = "") -> dict[str, str]:
    """Round-trip check: ``python -m app.cli check-worker`` enqueues this."""
    return {
        "status": "pong",
        "echo": payload,
        "host": socket.gethostname(),
        "pid": str(os.getpid()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
