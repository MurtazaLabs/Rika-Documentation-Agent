"""Versioned API router (``/api/v1``).

Projects, documents, uploads, ingestion jobs, retrieval, chat and
conversations live here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    chat,
    conversations,
    documents,
    jobs,
    projects,
    search,
    uploads,
)

api_router = APIRouter()
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(search.router)
api_router.include_router(chat.router)
api_router.include_router(conversations.router)
