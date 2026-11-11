"""FastAPI application entry point."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app import __version__
from app.api.routes import health
from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.core.constants import API_V1_PREFIX, STORAGE_SUBDIRECTORIES
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.database.session import create_engine, create_session_factory
from app.dependencies import AppResources
from app.llm.llama_client import ModelServerClient

logger = logging.getLogger("rika.api")

DESCRIPTION = (
    "Local project-intelligence RAG assistant. Ingests project documentation "
    "and source code, then answers questions with cited evidence."
)


def _validation_details(errors: list[dict[str, object]]) -> list[dict[str, object]]:
    """Drop Pydantic's non-JSON ``ctx`` and stringify odd input values."""
    details: list[dict[str, object]] = []
    for error in errors:
        entry: dict[str, object] = {
            "type": error.get("type", ""),
            "loc": [str(part) for part in error.get("loc", ())],  # type: ignore[union-attr]
            "msg": error.get("msg", ""),
        }
        if "input" in error:
            raw = error["input"]
            try:
                json.dumps(raw)
            except (TypeError, ValueError):
                raw = str(raw)
            entry["input"] = raw
        details.append(entry)
    return details


def _prepare_storage(settings: Settings) -> None:
    for name in STORAGE_SUBDIRECTORIES:
        (settings.storage_root / name).mkdir(parents=True, exist_ok=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _prepare_storage(settings)

        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.readiness_timeout,
            socket_timeout=settings.readiness_timeout,
        )
        chat_client = ModelServerClient(
            settings.chat_base_url,
            settings.chat_model_name,
            timeout=settings.chat_timeout,
            max_concurrency=settings.chat_max_concurrency,
        )
        embedding_client = ModelServerClient(
            settings.embedding_base_url,
            settings.embedding_model_name,
            timeout=settings.model_request_timeout,
            max_concurrency=settings.embedding_max_concurrency,
        )

        app.state.resources = AppResources(
            settings=settings,
            engine=engine,
            session_factory=session_factory,
            redis=redis,
            chat_client=chat_client,
            embedding_client=embedding_client,
        )

        logger.info(
            "%s %s starting (env=%s, storage=%s)",
            settings.app_name,
            __version__,
            settings.app_env,
            settings.storage_root,
        )
        if settings.embedding_dimension is None:
            logger.warning(
                "EMBEDDING_DIMENSION is not set; verify it with "
                "'python -m app.cli check-models' or ingestion will refuse to run"
            )

        try:
            yield
        finally:
            logger.info("shutting down")
            await chat_client.aclose()
            await embedding_client.aclose()
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        payload: dict[str, object] = {
            "error": {"code": exc.code, "message": exc.message}
        }
        if exc.details:
            payload["error"]["details"] = exc.details  # type: ignore[index]
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {"errors": _validation_details(exc.errors())},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                }
            },
        )

    app.include_router(health.router)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
