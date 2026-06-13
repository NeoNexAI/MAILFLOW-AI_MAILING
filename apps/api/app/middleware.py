"""Middlewares HTTP transversales (correlación de peticiones)."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import request_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Asigna un id de correlación por petición y lo expone en la respuesta.

    Reusa un `X-Request-ID` entrante (p.ej. del reverse proxy) o genera uno. Lo
    publica en una contextvar para que todos los logs de la petición lo lleven.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time-ms"] = str(
            round((time.monotonic() - started) * 1000, 1)
        )
        return response
