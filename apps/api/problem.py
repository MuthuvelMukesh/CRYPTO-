"""RFC 7807 Problem Details for HTTP APIs (application/problem+json).

Standardizes error responses across all Platform v3.0 endpoints.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config.exceptions import CryptoIntelligenceError


class ProblemException(Exception):
    """Exception explicitly carrying RFC 7807 problem detail fields."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        type_uri: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_uri = type_uri or f"https://httpstatuses.com/{status_code}"
        self.extra = extra or {}


def build_problem_response(
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    request_id: str | None = None,
    type_uri: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Construct an RFC 7807 compliant JSONResponse with media type application/problem+json."""
    content: dict[str, Any] = {
        "type": type_uri or f"https://httpstatuses.com/{status_code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if request_id:
        content["request_id"] = request_id
    if extra:
        content.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
        headers={"Content-Type": "application/problem+json"},
    )


async def problem_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle FastAPI / Starlette HTTPException as RFC 7807 problem+json."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    title = {
        status.HTTP_400_BAD_REQUEST: "Bad Request",
        status.HTTP_401_UNAUTHORIZED: "Unauthorized",
        status.HTTP_403_FORBIDDEN: "Forbidden",
        status.HTTP_404_NOT_FOUND: "Not Found",
        status.HTTP_405_METHOD_NOT_ALLOWED: "Method Not Allowed",
        status.HTTP_409_CONFLICT: "Conflict",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "Unprocessable Entity",
        status.HTTP_429_TOO_MANY_REQUESTS: "Too Many Requests",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal Server Error",
    }.get(exc.status_code, "HTTP Error")

    detail = str(exc.detail) if isinstance(exc.detail, str) else str(exc.detail)
    headers = getattr(exc, "headers", None) or {}
    resp = build_problem_response(
        status_code=exc.status_code,
        title=title,
        detail=detail,
        instance=request.url.path,
        request_id=request_id,
    )
    for k, v in headers.items():
        resp.headers[k] = v
    return resp


async def problem_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic RequestValidationError as RFC 7807 problem+json."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    errors = exc.errors()
    return build_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail="Request payload or parameters validation failed.",
        instance=request.url.path,
        request_id=request_id,
        extra={"invalid_params": errors},
    )


async def problem_crypto_error_handler(request: Request, exc: CryptoIntelligenceError) -> JSONResponse:
    """Handle domain CryptoIntelligenceError as RFC 7807 problem+json."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    return build_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title=type(exc).__name__,
        detail=str(exc),
        instance=request.url.path,
        request_id=request_id,
        extra={"details": getattr(exc, "details", None) or str(exc)},
    )


async def problem_generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions to prevent stack trace leaks in responses."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    return build_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected server error occurred. Please contact support with the request ID.",
        instance=request.url.path,
        request_id=request_id,
    )
