"""Authentication endpoints for token exchange and session validation."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from apps.api.auth import AuthIdentity, create_access_token, generate_csrf_token, verify_api_key
from apps.api.deps import get_current_auth

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class TokenRequest(BaseModel):
    """Payload to request a JWT token using an API key or researcher identity."""

    api_key: str = Field(..., description="Valid API key")
    subject: str = Field(default="quant-researcher", description="Client identifier or username")


class TokenResponse(BaseModel):
    """JWT Bearer access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    subject: str


class CsrfResponse(BaseModel):
    """CSRF token for browser session initialization."""

    csrf_token: str


@router.post("/token", response_model=TokenResponse, summary="Exchange API key for a JWT access token")
async def exchange_token(req: TokenRequest) -> TokenResponse:
    """Issue a signed JWT access token if the provided API key is valid."""
    if not verify_api_key(req.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    token = create_access_token(subject=req.subject)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=60 * 24 * 60,
        subject=req.subject,
    )


@router.get("/me", response_model=AuthIdentity, summary="Inspect current authenticated identity")
async def get_me(auth: Annotated[AuthIdentity, Depends(get_current_auth)]) -> AuthIdentity:
    """Return the caller's validated authentication identity and scopes."""
    return auth


@router.get("/csrf", response_model=CsrfResponse, summary="Obtain CSRF token for browser session")
async def get_csrf_token() -> CsrfResponse:
    """Generate a random CSRF token to be included in mutating requests from browser clients."""
    return CsrfResponse(csrf_token=generate_csrf_token())
