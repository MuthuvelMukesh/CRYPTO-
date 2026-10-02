"""FastAPI route dependencies for Platform v3.0."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.auth import AuthIdentity, verify_api_key, verify_jwt_token
from src.config.settings import get_settings
from src.database.cache import CacheService
from src.database.session import get_db

# Auto-extract Bearer token from Authorization header if present
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_auth(
    request: Request,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthIdentity:
    """Enforce hybrid authentication (API Key or JWT Bearer Token).

    Returns authenticated AuthIdentity or raises HTTP 401 Unauthorized.
    """
    # 1. Check X-API-Key header
    if x_api_key:
        if verify_api_key(x_api_key):
            return AuthIdentity(
                auth_type="api_key",
                identity=f"api_key:{x_api_key[:8]}...",
                scopes=["read", "write"],
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key provided in X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # 2. Check Bearer token from Authorization header
    if bearer and bearer.credentials:
        token = bearer.credentials.strip()

        # Check if Bearer token is an API key
        if verify_api_key(token):
            return AuthIdentity(
                auth_type="api_key",
                identity=f"api_key:{token[:8]}...",
                scopes=["read", "write"],
            )

        # Check if Bearer token is a valid signed JWT
        payload = verify_jwt_token(token)
        if payload is not None:
            sub = payload.get("sub", "unknown_user")
            scopes = payload.get("scopes", ["read", "write"])
            return AuthIdentity(
                auth_type="jwt",
                identity=sub,
                scopes=scopes,
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. No credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide a valid 'X-API-Key' or 'Authorization: Bearer <token>' header.",
        headers={"WWW-Authenticate": "Bearer, ApiKey"},
    )


async def get_optional_auth(
    request: Request,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthIdentity | None:
    """Optional authentication: returns AuthIdentity if valid credentials passed, None otherwise."""
    try:
        return await get_current_auth(request, bearer, x_api_key)
    except HTTPException:
        return None


__all__ = [
    "AuthIdentity",
    "CacheService",
    "get_current_auth",
    "get_db",
    "get_optional_auth",
    "get_settings",
]
