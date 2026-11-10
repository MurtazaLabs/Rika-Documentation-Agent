"""Versioned API router (``/api/v1``).

Projects, documents, uploads, ingestion jobs and retrieval live here. Chat and
conversations follow in later phases.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import documents, jobs, projects, search, uploads

api_router = APIRouter()
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(search.router)
