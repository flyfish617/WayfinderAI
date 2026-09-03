"""
Request ID middleware.
"""

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.logger import clear_request_id, set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to the request context and response headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid.uuid4())
        token = set_request_id(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_request_id(token)
