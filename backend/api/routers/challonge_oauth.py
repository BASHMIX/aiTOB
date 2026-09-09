"""Admin-initiated Challonge OAuth connection flow."""
from __future__ import annotations

import html
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from backend.api.auth import verify_hub_password
from backend.core.database import consume_oauth_state, create_oauth_state
from backend.core.providers.challonge.oauth import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_SCOPES,
    ChallongeOAuthError,
    callback_url,
    exchange_code,
    oauth_client_credentials,
    store_token_response,
)

router = APIRouter(tags=["challonge-oauth"])
_STATE_TTL_SECONDS = 10 * 60


def _page(title: str, message: str, ok: bool) -> HTMLResponse:
    color = "#10b981" if ok else "#ef4444"
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title>
<style>body{{font-family:system-ui;background:#0a0a0a;color:#eee;display:grid;place-items:center;min-height:100vh;margin:0}}main{{max-width:520px;padding:2rem;text-align:center;border:1px solid {color}55;border-radius:12px;background:#171717}}h1{{color:{color}}}</style>
</head><body><main><h1>{'Connected' if ok else 'Connection failed'}</h1><p>{html.escape(message)}</p></main></body></html>"""
    )


@router.get("/challonge/status", dependencies=[Depends(verify_hub_password)])
async def challonge_oauth_status(account_id: str | None = None):
    """Expose configuration state only; OAuth secrets and tokens never leave the server."""
    if not account_id:
        return {"client_configured": False, "redirect_configured": False, "connected": False, "callback_url": None}
    try:
        redirect_uri = await callback_url(account_id)
        configured_redirect = redirect_uri.startswith("https://")
    except ChallongeOAuthError:
        redirect_uri = None
        configured_redirect = False
    from backend.core.integrations import get_challonge_credential, get_challonge_oauth_application
    application = await get_challonge_oauth_application(account_id)
    token = await get_challonge_credential(account_id, "access_token")
    return {
        "client_configured": bool(application and application.get("configured")),
        "redirect_configured": configured_redirect,
        "connected": bool(token),
        "callback_url": redirect_uri if configured_redirect else None,
    }


@router.post("/challonge/connect", dependencies=[Depends(verify_hub_password)])
async def begin_challonge_oauth(account_id: str):
    """Create a single-use state value and return the provider authorization URL."""
    try:
        client_id, _ = await oauth_client_credentials(account_id)
        redirect_uri = await callback_url(account_id)
    except ChallongeOAuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not redirect_uri.startswith("https://"):
        raise HTTPException(400, "Challonge OAuth callback must use HTTPS.")

    state = secrets.token_urlsafe(32)
    await create_oauth_state("challonge", state, _STATE_TTL_SECONDS, account_id)
    return {
        "authorization_url": f"{OAUTH_AUTHORIZE_URL}?{urlencode({
            'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri,
            'scope': OAUTH_SCOPES, 'state': state,
        })}"
    }


@router.api_route("/challonge/callback", methods=["GET", "POST"])
async def complete_challonge_oauth(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = Query(default=None),
):
    """Validate a one-time state, exchange the code, and retain tokens server-side."""
    # OAuth normally redirects with a GET query string, but accepting the
    # equivalent form POST avoids a provider/browser 405 without weakening the
    # single-use state validation below.
    if request.method == "POST":
        form = await request.form()
        state = state or form.get("state")
        code = code or form.get("code")
        error = error or form.get("error")
    account_id = await consume_oauth_state("challonge", state) if state else None
    if not account_id:
        return _page("Challonge connection failed", "This OAuth link is invalid or has expired. Start again from aiTOB.", False)
    if error or not code:
        return _page("Challonge connection cancelled", "Challonge did not approve the requested access.", False)
    try:
        redirect_uri = await callback_url(account_id)
        token_response = await exchange_code(code, redirect_uri, account_id=account_id)
        await store_token_response(token_response, account_id)
    except ChallongeOAuthError as exc:
        return _page("Challonge connection failed", str(exc), False)
    return _page("Challonge connected", "The account is connected. You can close this tab and return to aiTOB.", True)
