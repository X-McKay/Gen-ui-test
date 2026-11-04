"""Authentication: customers through OAuth2 (group IdP), handlers by role."""

from __future__ import annotations

import os

from authlib.jose import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer

ISSUER = os.environ["OIDC_ISSUER"]
oauth2 = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{ISSUER}authorize", tokenUrl=f"{ISSUER}token"
)


def current_user(token: str = Depends(oauth2)) -> dict[str, object]:
    claims = jwt.decode(token, _jwks())
    claims.validate()
    return dict(claims)


def require_handler(user: dict[str, object] = Depends(current_user)) -> dict[str, object]:
    roles = user.get("roles") or []
    if "claims-handler" not in roles:
        raise HTTPException(status_code=403, detail="claims-handler role required")
    return user


def _jwks() -> dict[str, object]:  # pragma: no cover - fetched at startup in production
    raise NotImplementedError
