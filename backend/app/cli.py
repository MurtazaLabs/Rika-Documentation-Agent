"""Operator CLI.

Run from the ``backend`` directory (or with it on ``PYTHONPATH``)::

    python -m app.cli check-config
    python -m app.cli check-models
    python -m app.cli check-worker
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from urllib.parse import urlsplit, urlunsplit

from app.config import Settings, get_settings
from app.core.exceptions import ModelServerError
from app.llm.llama_client import ModelServerClient


def _mask_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"{parts.username}:***@{host}" if parts.username else host
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def check_config(settings: Settings) -> int:
    rows: list[tuple[str, str]] = [
        ("APP_NAME", settings.app_name),
        ("APP_ENV", settings.app_env),
        ("APP_DEBUG", str(settings.app_debug)),
        ("APP_HOST / APP_PORT", f"{settings.app_host}:{settings.app_port}"),
        ("DATABASE_URL", _mask_url(settings.database_url)),
        ("REDIS_URL", _mask_url(settings.redis_url)),
        ("CHAT_BASE_URL", settings.chat_base_url),
        ("CHAT_MODEL_NAME", settings.chat_model_name),
        ("EMBEDDING_BASE_URL", settings.embedding_base_url),
        ("EMBEDDING_MODEL_NAME", settings.embedding_model_name),
        (
            "EMBEDDING_DIMENSION",
            str(settings.embedding_dimension)
            if settings.embedding_dimension
            else "unverified (run check-models)",
        ),
        ("STORAGE_ROOT", str(settings.storage_root)),
        ("MAX_UPLOAD_MB", str(settings.max_upload_mb)),
        ("MAX_ARCHIVE_FILES", str(settings.max_archive_files)),
        ("MAX_ARCHIVE_EXPANDED_MB", str(settings.max_archive_expanded_mb)),
        (
            "CHUNK_SIZE_CHARS / CHUNK_OVERLAP_CHARS",
            f"{settings.chunk_size_chars} / {settings.chunk_overlap_chars}",
        ),
        ("EMBEDDING_BATCH_SIZE", str(settings.embedding_batch_size)),
        ("EMBEDDING_TIMEOUT", f"{settings.embedding_timeout:g}s"),
        ("LOG_LEVEL", settings.log_level),
    ]
    width = max(len(key) for key, _ in rows)
    for key, value in rows:
        print(f"{key.ljust(width)}  {value}")

    if settings.embedding_dimension is None:
        print(
            "\nwarning: EMBEDDING_DIMENSION is unset; ingestion cannot store "
            "vectors until check-models reports it"
        )
    return 0


async def _check_models(settings: Settings) -> int:
    chat = ModelServerClient(
        settings.chat_base_url, settings.chat_model_name,
        timeout=settings.model_request_timeout,
    )
    embedding = ModelServerClient(
        settings.embedding_base_url, settings.embedding_model_name,
        timeout=settings.model_request_timeout,
    )
    exit_code = 0
    try:
        for label, client in (("chat", chat), ("embedding", embedding)):
            try:
                models = await client.list_models()
            except ModelServerError as exc:
                print(f"[fail] {label:<9} {client.base_url}: {exc.message}")
                exit_code = 1
                continue
            listing = ", ".join(models) if models else "(no models loaded)"
            print(f"[ok]   {label:<9} {client.base_url}: {listing}")
            if models and client.model_name not in models:
                print(
                    f"       warning: configured name '{client.model_name}' "
                    f"is not in the server list"
                )

        try:
            vectors = await embedding.embed(["Rika embedding dimension probe"])
        except ModelServerError as exc:
            print(f"[fail] dimension  {exc.message}")
            return 1

        dimension = len(vectors[0])
        print(f"[ok]   dimension  {dimension}")
        if settings.embedding_dimension is None:
            print(
                f"       set EMBEDDING_DIMENSION={dimension} in .env before ingesting"
            )
        elif settings.embedding_dimension != dimension:
            print(
                f"[fail] EMBEDDING_DIMENSION={settings.embedding_dimension} "
                f"does not match the model output ({dimension})"
            )
            exit_code = 1
        else:
            print("       matches EMBEDDING_DIMENSION")
    finally:
        await chat.aclose()
        await embedding.aclose()
    return exit_code


def check_worker(settings: Settings) -> int:
    """Enqueue ``rika.ping`` and wait for the worker's result."""
    from app.workers.tasks import ping

    print(f"broker: {_mask_url(settings.redis_url)}")
    try:
        result = ping.delay("cli").get(timeout=10)
    except Exception as exc:  # noqa: BLE001 - broker errors vary by transport
        print(f"[fail] worker check: {exc.__class__.__name__}: {exc}")
        print("       is Redis running and is a celery worker started?")
        return 1
    print(f"[ok]   worker replied: {result}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    parser.add_argument(
        "command",
        choices=["check-config", "check-models", "check-worker"],
        help="which check to run",
    )
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "check-config":
        return check_config(settings)
    if args.command == "check-models":
        return asyncio.run(_check_models(settings))
    return check_worker(settings)


if __name__ == "__main__":
    sys.exit(main())
