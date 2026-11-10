"""Application error types.

Every error the API raises intentionally derives from :class:`AppError` so the
handler in ``app.main`` can turn it into a stable JSON shape.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected application failures."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details


class ConfigurationError(AppError):
    """Required configuration is missing or invalid."""

    status_code = 500
    code = "configuration_error"


class NotFoundError(AppError):
    """The requested resource does not exist (or is outside the project scope)."""

    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """The request is valid but conflicts with the resource's current state."""

    status_code = 409
    code = "conflict"


class InvalidUploadError(AppError):
    """An upload failed validation (format, path, archive structure)."""

    status_code = 422
    code = "invalid_upload"


class PayloadTooLargeError(AppError):
    """An upload or its expanded archive exceeds the configured limits."""

    status_code = 413
    code = "file_too_large"


class DependencyUnavailable(AppError):
    """A required backing service (database, queue, model server) is down."""

    status_code = 503
    code = "dependency_unavailable"


class ModelServerError(AppError):
    """A local model server returned an error or could not be reached."""

    status_code = 502
    code = "model_server_error"
