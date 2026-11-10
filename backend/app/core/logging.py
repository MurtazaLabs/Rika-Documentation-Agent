"""Logging configuration with request-id correlation."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] rid=%(request_id)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once, writing to stdout."""
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
