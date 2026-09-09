"""Session-backed API authentication with a tightly scoped legacy bridge."""

from __future__ import annotations

import hmac
import os
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from backend.core.database import get_setting
from backend.core.workspace_auth import (
    SESSION_COOKIE, SessionPrincipal, get_session_principal,
    legacy_owner_principal, permission_allowed,
)

api_key_header = APIKeyHeader(name="X-Hub-Password", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})


async def current_session_principal(
    request: Request,
    auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> SessionPrincipal:
    token = request.cookies.get(SESSION_COOKIE) or (auth.credentials if auth else None)
    principal = await get_session_principal(token)
    if not principal:
        raise _unauthorized()
    return principal


async def optional_session_principal(
    request: Request,
    auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> SessionPrincipal | None:
    """Return a session principal when present; anonymous callers see no tenant data."""
    token = request.cookies.get(SESSION_COOKIE) or (auth.credentials if auth else None)
    return await get_session_principal(token)


async def verify_hub_password(
    request: Request,
    password_header: str | None = Depends(api_key_header),
    auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> SessionPrincipal | None:
    """Return a trusted principal; legacy password is opt-in owner-only bridge."""
    if request.url.path.startswith("/obs/") or request.url.path.startswith("/api/overlays/public"):
        return None
    candidate = request.cookies.get(SESSION_COOKIE) or (auth.credentials if auth else None)
    principal = await get_session_principal(candidate)
    if principal:
        # Existing Hub routes still read global/unscoped records. Fail closed
        # for non-owners until their data ownership migration is complete.
        if principal.role != "owner":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Legacy Hub routes are limited to the Owner workspace during migration")
        return principal

    # Compatibility is disabled by default, has no default password, and maps
    # only to exactly one active Owner membership. Remove after old clients move.
    if os.getenv("AITOB_LEGACY_HUB_PASSWORD_COMPAT", "false").lower() != "true":
        raise _unauthorized()
    supplied = password_header or (auth.credentials if auth else None)
    expected = await get_setting("HUB_PASSWORD") or await get_setting("hub_password") or os.getenv("HUB_PASSWORD")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        print(f"[AUTH] Denied request to {request.url.path}")
        raise _unauthorized()
    legacy = await legacy_owner_principal()
    if not legacy:
        raise _unauthorized()
    return legacy


def require_permission(permission: str) -> Callable:
    """Central role gate for incremental route migration."""
    async def dependency(
        request: Request,
        auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        password_header: str | None = Depends(api_key_header),
    ) -> SessionPrincipal:
        candidate = request.cookies.get(SESSION_COOKIE) or (auth.credentials if auth else None)
        principal = await get_session_principal(candidate)
        if not principal:
            # Existing tests and the owner-only migration bridge may still use
            # X-Hub-Password.  Keep this explicitly opt-in and owner-scoped;
            # normal deployments must use an account session.
            if os.getenv("AITOB_LEGACY_HUB_PASSWORD_COMPAT", "false").lower() != "true":
                raise _unauthorized()
            supplied = password_header or (auth.credentials if auth else None)
            expected = await get_setting("HUB_PASSWORD") or await get_setting("hub_password") or os.getenv("HUB_PASSWORD")
            if not supplied or not expected or not hmac.compare_digest(supplied, expected):
                raise _unauthorized()
            principal = await legacy_owner_principal()
            if not principal:
                raise _unauthorized()
        if not permission_allowed(principal.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return principal
    return dependency


async def require_platform_admin(
    principal: SessionPrincipal = Depends(current_session_principal),
) -> SessionPrincipal:
    """Gate service-scoped configuration separately from workspace ownership."""
    from backend.core.database import is_active_platform_admin
    if not await is_active_platform_admin(principal.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator permission required")
    return principal

