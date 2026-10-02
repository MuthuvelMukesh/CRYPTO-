"""Middleware layer for Platform v3.0 API.

Features:
- Request ID tracing (X-Request-ID propagation and structured logging)
- In-memory sliding window rate limiting (per client IP / API key)
- CSRF defense for browser sessions on mutating requests
"""

import time
import uuid
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.problem import build_problem_response
from src.config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger("apps.api.middleware")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns or propagates X-Request-ID header and binds it to request state."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = str(uuid.uuid4())

        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter per client IP / API key."""

    def __init__(self, app) -> None:
        super().__init__(app)
        # client_id -> list of unix timestamps
        self._history: dict[str, list[float]] = defaultdict(list)
        self._window_seconds: float = 60.0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Exempt health and docs endpoints from rate limiting
        path = request.url.path
        if path.startswith(("/health", "/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        settings = get_settings()
        limit = settings.API_RATE_LIMIT_PER_MINUTE

        # Client identifier: API key header if present, otherwise client host IP
        client_id = (
            request.headers.get("X-API-Key")
            or (request.client.host if request.client else "unknown_client")
        )

        now = time.time()
        cutoff = now - self._window_seconds

        # Prune older entries
        timestamps = [t for t in self._history[client_id] if t > cutoff]
        self._history[client_id] = timestamps

        if len(timestamps) >= limit:
            retry_after = int(self._window_seconds - (now - timestamps[0])) + 1
            request_id = getattr(request.state, "request_id", None)
            logger.warning(
                "rate_limit_exceeded",
                client_id=client_id,
                path=path,
                request_id=request_id,
                retry_after=retry_after,
            )
            resp = build_problem_response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                title="Too Many Requests",
                detail=f"Rate limit of {limit} requests per minute exceeded. Please retry after {retry_after} seconds.",
                instance=path,
                request_id=request_id,
            )
            resp.headers["Retry-After"] = str(max(1, retry_after))
            return resp

        self._history[client_id].append(now)
        return await call_next(request)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Protects state-mutating requests from CSRF when browser cookies are involved."""

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.CSRF_PROTECTION_ENABLED:
            return await call_next(request)

        # Only check mutating methods
        if request.method not in self.MUTATING_METHODS:
            return await call_next(request)

        # Exempt health, auth token exchange, and backtest endpoints if using Authorization headers
        path = request.url.path
        if path.startswith(("/health", "/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        # If call uses Bearer token or X-API-Key, it is programmatic and immune to ambient cookie CSRF
        auth_header = request.headers.get("Authorization") or ""
        api_key_header = request.headers.get("X-API-Key") or ""
        if auth_header.startswith("Bearer ") or api_key_header:
            return await call_next(request)

        # If a session/auth cookie is present, require matching X-CSRF-Token header
        session_cookie = request.cookies.get("session_id") or request.cookies.get("csrftoken")
        if session_cookie:
            header_token = request.headers.get("X-CSRF-Token")
            if not header_token or header_token != session_cookie:
                request_id = getattr(request.state, "request_id", None)
                return build_problem_response(
                    status_code=status.HTTP_403_FORBIDDEN,
                    title="Forbidden",
                    detail="CSRF validation failed: missing or invalid X-CSRF-Token header.",
                    instance=path,
                    request_id=request_id,
                )

        return await call_next(request)
