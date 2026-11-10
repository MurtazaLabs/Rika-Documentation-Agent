"""Request-id middleware."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.constants import REQUEST_ID_HEADER
from app.core.logging import request_id_var


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Reuse an incoming request id or generate one, and echo it back."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        request_id = incoming[:64] if incoming else uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
