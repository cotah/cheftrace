"""Supabase JWT verification via JWKS with HS256 fallback."""
from typing import Any, cast

import httpx
from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings

_jwks_cache: list[dict[str, Any]] | None = None


async def _fetch_jwks() -> list[dict[str, Any]]:
    """Fetch public keys from Supabase JWKS endpoint. Cached in memory."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        )
        response.raise_for_status()
        data = response.json()
        _jwks_cache = data.get("keys", [])
    return _jwks_cache


async def verify_supabase_token(token: str) -> dict[str, Any]:
    """Verify Supabase JWT. Tries ES256/RS256 via JWKS, falls back to HS256."""
    # Try JWKS-based verification (ES256 / RS256 — current Supabase default)
    try:
        keys = await _fetch_jwks()
        for key in keys:
            try:
                payload = jwt.decode(
                    token,
                    key,
                    algorithms=["ES256", "RS256"],
                    audience="authenticated",
                )
                return cast(dict[str, Any], payload)
            except ExpiredSignatureError as err:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired",
                ) from err
            except JWTError:
                continue
    except HTTPException:
        raise
    except Exception:
        pass

    # Fallback: legacy HS256 shared secret (tokens issued before key rotation)
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return cast(dict[str, Any], payload)
    except ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from err
    except JWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from err
