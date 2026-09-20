"""Workspace-owned OAuth sign-in for tournament providers."""
from __future__ import annotations

import hashlib
import html
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.api.auth import require_permission
from backend.core import database, integrations
from backend.core.storage import dbapi as aiosqlite
from backend.core.tournament_setup import DraftNotFound, get_draft
from backend.core.workspace_auth import SessionPrincipal

router = APIRouter(tags=["provider-oauth"])
_STATE_TTL_SECONDS = 10 * 60
_STARTGG_AUTHORIZE = "https://start.gg/oauth/authorize"
_STARTGG_TOKEN = "https://api.start.gg/oauth/access_token"
_STARTGG_GQL = "https://api.start.gg/gql/alpha"
_CHALLONGE_AUTHORIZE = "https://api.challonge.com/oauth/authorize"
_CHALLONGE_TOKEN = "https://api.challonge.com/oauth/token"
_STARTGG_SCOPE = "user.identity tournament.manager tournament.reporter"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _secret(key: str) -> str | None:
    return await database.get_setting(key) or await database.get_connection(key) or os.getenv(key)


async def _callback_url(provider: str) -> str:
    configured = await _secret(f"{provider.upper()}_OAUTH_REDIRECT_URI")
    if configured:
        return configured.rstrip("/")
    base = (await _secret("API_BASE_URL")) or "http://localhost:8000"
    return f"{base.rstrip('/')}/api/auth/providers/{provider}/callback"


async def _save_state(state: str, provider: str, workspace_id: str, draft_id: str | None, return_step: str) -> None:
    expires = int(time.time()) + _STATE_TTL_SECONDS
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("DELETE FROM provider_oauth_states WHERE expires_at <= ?", (int(time.time()),))
        await db.execute(
            "INSERT INTO provider_oauth_states (state_hash, provider, workspace_id, draft_id, return_step, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_hash(state), provider, workspace_id, draft_id, return_step, expires),
        )
        await db.commit()


async def _consume_state(provider: str, state: str) -> dict | None:
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT * FROM provider_oauth_states WHERE state_hash=? AND provider=? AND expires_at>?",
            (_hash(state), provider, int(time.time())),
        )).fetchone()
        if row:
            await db.execute("DELETE FROM provider_oauth_states WHERE state_hash=?", (_hash(state),))
        await db.execute("DELETE FROM provider_oauth_states WHERE expires_at<=?", (int(time.time()),))
        await db.commit()
    return dict(row) if row else None


def _frontend_redirect(state: dict, *, provider: str, outcome: str, account_id: str | None = None) -> RedirectResponse:
    base = (os.getenv("FRONTEND_BASE_URL") or "http://localhost:5173").rstrip("/")
    draft = state.get("draft_id")
    step = state.get("return_step") or "provider"
    path = f"/admin/tournaments/setup/{draft}/{step}" if draft else "/admin/hub"
    query = {"provider_oauth": outcome, "provider": provider}
    if account_id:
        query["account_id"] = account_id
    return RedirectResponse(f"{base}{path}?{urlencode(query)}", status_code=303)


@router.post("/providers/{provider}/connect")
async def begin_provider_oauth(
    provider: str,
    body: dict[str, str] | None = None,
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    provider = provider.strip().lower()
    if provider not in {"startgg", "challonge"}:
        raise HTTPException(422, "Unsupported provider OAuth flow.")
    body = body or {}
    draft_id = str(body.get("draft_id") or "").strip() or None
    return_step = str(body.get("return_step") or "provider").strip()
    if return_step not in {"provider", "tournament", "review"}:
        raise HTTPException(422, "Invalid wizard return step.")
    if draft_id:
        try:
            await get_draft(draft_id, principal.workspace_id)
        except DraftNotFound as exc:
            raise HTTPException(404, "Draft not found") from exc

    if provider == "startgg":
        client_id = await _secret("STARTGG_CLIENT_ID")
        scope = _STARTGG_SCOPE
    else:
        client_id = await _secret("CHALLONGE_OAUTH_CLIENT_ID")
        scope = "me application:organizer tournaments:read tournaments:write matches:read matches:write participants:read participants:write"
    if not client_id:
        raise HTTPException(409, f"{provider} OAuth application is not configured.")
    state = secrets.token_urlsafe(32)
    await _save_state(state, provider, principal.workspace_id, draft_id, return_step)
    callback = await _callback_url(provider)
    authorize = _STARTGG_AUTHORIZE if provider == "startgg" else _CHALLONGE_AUTHORIZE
    return {
        "authorization_url": f"{authorize}?{urlencode({'response_type': 'code', 'client_id': client_id, 'redirect_uri': callback, 'scope': scope, 'state': state})}",
        "expires_in": _STATE_TTL_SECONDS,
    }


async def _exchange_startgg(code: str, redirect_uri: str) -> dict:
    client_id, client_secret = await _secret("STARTGG_CLIENT_ID"), await _secret("STARTGG_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Start.gg OAuth application is not configured.")
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.post(_STARTGG_TOKEN, json={
            "grant_type": "authorization_code", "code": code,
            "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "scope": _STARTGG_SCOPE,
        }, headers={"Content-Type": "application/json"})
    if response.is_error:
        raise RuntimeError("Start.gg rejected the OAuth authorization code.")
    return response.json()


async def _startgg_identity(token: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.post(_STARTGG_GQL, json={"query": "query { currentUser { id name slug player { gamerTag } } }"}, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if response.is_error or "errors" in response.json():
        raise RuntimeError("Start.gg could not verify the connected account.")
    identity = (response.json().get("data") or {}).get("currentUser")
    if not identity or identity.get("id") is None:
        raise RuntimeError("Start.gg returned no connected account identity.")
    return identity


async def _exchange_challonge(code: str, redirect_uri: str) -> dict:
    client_id, client_secret = await _secret("CHALLONGE_OAUTH_CLIENT_ID"), await _secret("CHALLONGE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Challonge OAuth application is not configured.")
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.post(_CHALLONGE_TOKEN, data={
            "grant_type": "authorization_code", "code": code,
            "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }, headers={"Accept": "application/json"})
    if response.is_error:
        raise RuntimeError("Challonge rejected the OAuth authorization code.")
    return response.json()


async def _challonge_identity(token: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.get("https://api.challonge.com/v2.1/me.json", headers={
            "Authorization": f"Bearer {token}", "Authorization-Type": "v2", "Accept": "application/json",
        })
    if response.is_error:
        return {"id": "oauth-user", "name": "Challonge account"}
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    attrs = (data or {}).get("attributes") if isinstance(data, dict) else {}
    return {"id": (data or {}).get("id") or "oauth-user", "name": (attrs or {}).get("username") or (attrs or {}).get("email") or "Challonge account"}


async def _upsert_oauth_account(provider: str, workspace_id: str, token: dict) -> str:
    access_token = str(token.get("access_token") or "")
    if not access_token:
        raise RuntimeError(f"{provider} did not return an access token.")
    identity = await (_startgg_identity(access_token) if provider == "startgg" else _challonge_identity(access_token))
    external_id = str(identity.get("id") or "oauth-user")
    startgg_player = identity.get("player") or {}
    display_name = str(
        (startgg_player.get("gamerTag") or identity.get("name") or identity.get("slug"))
        if provider == "startgg" else (identity.get("name") or f"{provider} account")
    )
    accounts = await integrations.list_integration_accounts(workspace_id)
    account = next((item for item in accounts if item["provider_type"] == provider and item["external_account_id"] == external_id), None)
    if account:
        account_id = str(account["id"])
        await integrations.update_integration_account(account_id, workspace_id=workspace_id, display_name=display_name)
    else:
        account = await integrations.create_integration_account(workspace_id, provider, external_id, display_name)
        account_id = str(account["id"])
    await integrations.set_integration_secret(account_id, "access_token", access_token, workspace_id=workspace_id)
    if token.get("refresh_token"):
        await integrations.set_integration_secret(account_id, "refresh_token", str(token["refresh_token"]), workspace_id=workspace_id)
    return account_id


def _result_page(title: str, message: str, ok: bool) -> HTMLResponse:
    color = "#10b981" if ok else "#ef4444"
    return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title></head><body style='font-family:system-ui;background:#0a0a0a;color:#eee;display:grid;place-items:center;min-height:100vh'><main style='max-width:520px;padding:2rem;text-align:center;border:1px solid {color}55;border-radius:12px;background:#171717'><h1 style='color:{color}'>{html.escape(title)}</h1><p>{html.escape(message)}</p></main></body></html>")


@router.get("/providers/{provider}/callback")
async def provider_oauth_callback(provider: str, code: str | None = Query(default=None), state: str | None = Query(default=None), error: str | None = Query(default=None)):
    provider = provider.strip().lower()
    if provider not in {"startgg", "challonge"} or not state:
        raise HTTPException(400, "Invalid OAuth callback.")
    saved = await _consume_state(provider, state)
    if not saved:
        raise HTTPException(400, "OAuth state is invalid or expired.")
    if error or not code:
        return _frontend_redirect(saved, provider=provider, outcome="cancelled")
    try:
        redirect_uri = await _callback_url(provider)
        token = await (_exchange_startgg(code, redirect_uri) if provider == "startgg" else _exchange_challonge(code, redirect_uri))
        account_id = await _upsert_oauth_account(provider, str(saved["workspace_id"]), token)
    except Exception:
        return _frontend_redirect(saved, provider=provider, outcome="failed")
    return _frontend_redirect(saved, provider=provider, outcome="connected", account_id=account_id)
