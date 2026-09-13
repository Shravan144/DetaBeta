"""Backend JWT authentication.

The frontend (NextAuth) issues short-lived JWTs signed with a shared secret
(BACKEND_JWT_SECRET). Every backend request carries this token in the
Authorization header. This module validates those tokens and exposes the
authenticated identity as a FastAPI dependency.

The backend never stores users in its own database -- it trusts the identity
claims in the JWT issued by the frontend. The user's provider-scoped ID
(``sub``) is what we use to scope data ownership.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer(auto_error=False)

_ISSUER = "detabeta-frontend"
_AUDIENCE = "detabeta-api"
_ALGORITHM = "HS256"


@dataclass(frozen=True)
class UserIdentity:
    """The authenticated caller's identity, extracted from a valid JWT."""

    sub: str
    email: str | None = None
    name: str | None = None


def _get_secret() -> str:
    """Return the shared JWT secret, or raise if it is missing/too short."""
    secret = os.environ.get("BACKEND_JWT_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BACKEND_JWT_SECRET is not configured or is shorter than 32 characters.",
        )
    return secret


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserIdentity:
    """FastAPI dependency: decode and validate the Bearer JWT.

    Returns a UserIdentity on success. Raises HTTP 401 for any auth failure
    (missing header, bad token, expired, wrong issuer/audience).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = _get_secret()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
            audience=_AUDIENCE,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing subject claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserIdentity(
        sub=str(sub),
        email=payload.get("email"),
        name=payload.get("name"),
    )
