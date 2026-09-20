"""Managed Discord OAuth state and callback boundary.

The actual Discord token exchange belongs to the deployment's bot service; the
API owns only the short-lived, hashed state and safe redirect outcome.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from backend.api.auth import require_permission
from backend.core import database
from backend.core.storage import dbapi as aiosqlite
from backend.core.tournament_setup import DraftNotFound, get_draft
from backend.core.workspace_auth import SessionPrincipal

router = APIRouter(tags=["discord-oauth"])


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("/integrations/discord/authorize")
async def authorize_discord(
    body: dict[str, str],
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    draft_id = str(body.get("draft_id") or "").strip()
    return_step = str(body.get("return_step") or "discord").strip()
    if return_step not in {"discord", "review"}:
        raise HTTPException(422, "invalid_return_step")
    try:
        await get_draft(draft_id, principal.workspace_id)
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    opaque = secrets.token_urlsafe(32)
    expires = int(time.time()) + 600
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("DELETE FROM discord_oauth_states WHERE expires_at <= ?", (int(time.time()),))
        await db.execute(
            "INSERT INTO discord_oauth_states (state_hash, workspace_id, actor_id, draft_id, return_step, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_hash(opaque), principal.workspace_id, principal.user_id, draft_id, return_step, expires),
        )
        await db.commit()
    base = str(__import__("os").getenv("DISCORD_OAUTH_AUTHORIZE_URL") or "https://discord.com/oauth2/authorize")
    query = urlencode({"state": opaque, "response_type": "code", "scope": "bot applications.commands"})
    return {"authorization_url": f"{base}?{query}", "expires_in": 600}


@router.get("/integrations/discord/callback")
async def discord_callback(code: str | None = Query(default=None), state: str | None = Query(default=None)):
    if not state:
        raise HTTPException(400, "oauth_state_missing")
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT * FROM discord_oauth_states WHERE state_hash=? AND expires_at>?",
            (_hash(state), int(time.time())),
        )).fetchone()
        if row:
            await db.execute("DELETE FROM discord_oauth_states WHERE state_hash=?", (_hash(state),))
        await db.execute("DELETE FROM discord_oauth_states WHERE expires_at<=?", (int(time.time()),))
        await db.commit()
    if not row:
        raise HTTPException(400, "oauth_state_invalid_or_expired")
    # Deployment code can exchange the one-time provider code.  Never echo it
    # into a response or log; only expose an enumerated outcome to the UI.
    outcome = "authorized" if code else "missing_code"
    target = f"/admin/tournaments/setup/{row['draft_id']}/{row['return_step']}?discord={outcome}"
    return RedirectResponse(target, status_code=303)
