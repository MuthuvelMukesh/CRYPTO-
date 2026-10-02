"""Authentication, authorization, and cryptographic utilities for Platform v3.0 API.

Supports Hybrid Authentication:
1. Programmatic API Keys (via `X-API-Key` or `Authorization: Bearer <key>`)
2. JWT Tokens (via `Authorization: Bearer <jwt>`) for sessions / UI
3. CSRF token validation for browser mutating requests
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pydantic import BaseModel, Field

from src.config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger("apps.api.auth")


class AuthIdentity(BaseModel):
    """Authenticated caller identity representation."""

    auth_type: Literal["api_key", "jwt"] = Field(..., description="Authentication mechanism used")
    identity: str = Field(..., description="Subject or API key identifier")
    scopes: list[str] = Field(default_factory=lambda: ["read", "write"])
    authenticated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def create_access_token(
    subject: str,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Generate a signed JWT access token."""
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    claims: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "scopes": scopes or ["read", "write"],
    }
    if extra_claims:
        claims.update(extra_claims)

    encoded_jwt = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT bearer token. Returns payload dict or None if invalid."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        return payload
    except (jwt.PyJWTError, Exception) as exc:
        logger.debug("jwt_token_verification_failed", error=str(exc))
        return None


def verify_api_key(api_key: str) -> bool:
    """Verify whether the provided API key is registered in settings."""
    settings = get_settings()
    if not api_key:
        return False
    # Constant-time comparison to prevent timing attacks
    for valid_key in settings.api_keys_list:
        if secrets.compare_digest(api_key, valid_key):
            return True
    return False


def generate_csrf_token() -> str:
    """Generate a cryptographically secure random token for CSRF defense."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    """Double-submit cookie CSRF validation pattern."""
    if not cookie_token or not header_token:
        return False
    return secrets.compare_digest(cookie_token, header_token)
