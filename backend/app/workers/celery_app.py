"""Celery application for background ingestion.

Run with::

    celery -A app.workers.celery_app worker --loglevel=INFO

Windows has no ``fork``, so the ``solo`` pool is selected automatically.
"""

from __future__ import annotations

import os

from celery import Celery

from app import __version__
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rika",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # 4 GB VRAM / 16 GB RAM: keep heavy ingestion work serialised by default.
    worker_concurrency=1,
    task_time_limit=1800,
    task_soft_time_limit=1500,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    broker_transport_options={"visibility_timeout": 3600},
)

if os.name == "nt":  # pragma: no cover - platform specific
    celery_app.conf.worker_pool = "solo"

celery_app.conf.update(worker_hijack_root_logger=False)

__all__ = ["celery_app", "__version__"]
