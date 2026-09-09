"""Server-side OAuth support for the Challonge provider.

Tokens are intentionally kept in the local connections store.  They are never
returned by the Hub API and never written to logs, browser state, or URLs.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

OAUTH_AUTHORIZE_URL = "https://api.challonge.com/oauth/authorize"
OAUTH_TOKEN_URL = "https://api.challonge.com/oauth/token"
# Community-hosted FNC brackets require this scope in addition to tournament
# scopes; Challonge presents a community selector when it is granted.
OAUTH_SCOPES = "tournaments:read tournaments:write matches:read matches:write participants:read communities:manage"
_REFRESH_SKEW_SECONDS = 60
_refresh_lock = asyncio.Lock()


class ChallongeOAuthError(Exception):
    """A user-safe OAuth configuration or token error."""


async def resolve_secret(key: str, default: str | None = None) -> str | None:
    """Resolve configured values without exposing them outside the backend."""
    from backend.core.database import get_connection, get_setting

    return await get_connection(key) or await get_setting(key) or os.getenv(key, default)


async def callback_url(account_id: str | None = None) -> str:
    if account_id:
        from backend.core.integrations import get_challonge_oauth_application
        application = await get_challonge_oauth_application(account_id)
        if application:
            return str(application["redirect_uri"]).rstrip("/")
    explicit = await resolve_secret("CHALLONGE_OAUTH_REDIRECT_URI")
    if explicit:
        return explicit.rstrip("/")

    base_url = await resolve_secret("API_BASE_URL")
    if not base_url:
        raise ChallongeOAuthError(
            "Set CHALLONGE_OAUTH_REDIRECT_URI to the HTTPS callback URL before connecting Challonge."
        )
    return f"{base_url.rstrip('/')}/api/auth/challonge/callback"


async def oauth_client_credentials(account_id: str | None = None) -> tuple[str, str]:
    if account_id:
        from backend.core.integrations import get_challonge_oauth_application, get_integration_secret
        application = await get_challonge_oauth_application(account_id)
        if not application:
            raise ChallongeOAuthError("Challonge OAuth application is not configured for this account.")
        secret = await get_integration_secret(application["id"], "client_secret", owner_kind="application")
        if not secret:
            raise ChallongeOAuthError("Challonge OAuth application secret is not configured.")
        return str(application["client_id"]), secret
    client_id = await resolve_secret("CHALLONGE_OAUTH_CLIENT_ID")
    client_secret = await resolve_secret("CHALLONGE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ChallongeOAuthError("Challonge OAuth client ID and secret are not configured.")
    return client_id, client_secret


async def exchange_code(code: str, redirect_uri: str, *, account_id: str | None = None) -> dict[str, Any]:
    client_id, client_secret = await oauth_client_credentials(account_id)
    async with httpx.AsyncClient(timeout=20.0) as http:
        response = await http.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    if response.is_error:
        raise ChallongeOAuthError("Challonge rejected the OAuth authorization code.")
    payload = response.json()
    if not payload.get("access_token"):
        raise ChallongeOAuthError("Challonge did not return an OAuth access token.")
    return payload


async def _persist_tokens(payload: dict[str, Any], account_id: str | None = None) -> None:
    if account_id:
        from backend.core.integrations import set_integration_secret
        access_token = str(payload.get("access_token") or "")
        if not access_token:
            raise ChallongeOAuthError("Challonge did not return an OAuth access token.")
        await set_integration_secret(account_id, "access_token", access_token)
        if payload.get("refresh_token"):
            await set_integration_secret(account_id, "refresh_token", str(payload["refresh_token"]))
        return
    from backend.core.database import set_connection

    access_token = str(payload.get("access_token") or "")
    if not access_token:
        raise ChallongeOAuthError("Challonge did not return an OAuth access token.")
    await set_connection("CHALLONGE_OAUTH_ACCESS_TOKEN", access_token)

    refresh_token = payload.get("refresh_token")
    if refresh_token:
        await set_connection("CHALLONGE_OAUTH_REFRESH_TOKEN", str(refresh_token))

    expires_in = payload.get("expires_in")
    if expires_in is not None:
        try:
            expires_at = int(time.time()) + max(0, int(expires_in))
            await set_connection("CHALLONGE_OAUTH_EXPIRES_AT", str(expires_at))
        except (TypeError, ValueError):
            # An absent/malformed expiry is safer than persisting a guessed date.
            await set_connection("CHALLONGE_OAUTH_EXPIRES_AT", "")


async def store_token_response(payload: dict[str, Any], account_id: str | None = None) -> None:
    """Persist a successful authorization-code response without exposing it."""
    await _persist_tokens(payload, account_id)


async def _refresh_access_token() -> str | None:
    from backend.core.database import get_connection

    refresh_token = await get_connection("CHALLONGE_OAUTH_REFRESH_TOKEN")
    if not refresh_token:
        return None
    client_id, client_secret = await oauth_client_credentials()
    async with httpx.AsyncClient(timeout=20.0) as http:
        response = await http.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
        )
    if response.is_error:
        raise ChallongeOAuthError("Challonge OAuth token expired. Connect Challonge again.")
    payload = response.json()
    await _persist_tokens(payload)
    return str(payload["access_token"])


async def valid_access_token(account_id: str | None = None) -> str | None:
    """Return a usable OAuth token, refreshing it once when it is near expiry."""
    from backend.core.database import get_connection

    if account_id:
        from backend.core.integrations import get_challonge_credential
        return await get_challonge_credential(account_id, "access_token")
    token = await get_connection("CHALLONGE_OAUTH_ACCESS_TOKEN")
    if not token:
        return None
    raw_expiry = await get_connection("CHALLONGE_OAUTH_EXPIRES_AT")
    try:
        expires_at = int(raw_expiry) if raw_expiry else None
    except ValueError:
        expires_at = None
    if expires_at is None or expires_at > int(time.time()) + _REFRESH_SKEW_SECONDS:
        return token

    async with _refresh_lock:
        # Another request may have refreshed the token while this one waited.
        current_token = await get_connection("CHALLONGE_OAUTH_ACCESS_TOKEN")
        current_expiry = await get_connection("CHALLONGE_OAUTH_EXPIRES_AT")
        try:
            if current_token and int(current_expiry) > int(time.time()) + _REFRESH_SKEW_SECONDS:
                return current_token
        except (TypeError, ValueError):
            pass
        return await _refresh_access_token()
