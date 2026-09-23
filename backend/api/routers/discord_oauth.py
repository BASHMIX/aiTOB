"""Managed Discord installation OAuth and workspace binding."""
from __future__ import annotations

import hashlib
import secrets
import time
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from backend.api.auth import require_permission
from backend.core import database
from backend.core.storage import dbapi
from backend.core.discord_api import (
    DiscordAPIError, authorization_url, authorize_installer, discover_guild, exchange_code,
)
from backend.core.integrations import (
    create_integration_account, enable_integration_account, list_integration_accounts,
    update_integration_account,
)
from backend.core.tournament_setup import DraftNotFound, DraftRevisionConflict, get_draft, patch_draft
from backend.core.workspace_auth import SessionPrincipal

router = APIRouter(tags=["discord-oauth"])


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("/integrations/discord/authorize")
async def authorize_discord(
    body: dict[str, str],
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    draft_id = str(body.get("draft_id") or "").strip() or None
    return_step = str(body.get("return_step") or ("discord" if draft_id else "connections")).strip()
    if return_step not in {"discord", "review", "connections"}:
        raise HTTPException(422, "invalid_return_step")
    if draft_id:
        try:
            await get_draft(draft_id, principal.workspace_id)
        except DraftNotFound as exc:
            raise HTTPException(404, "Draft not found") from exc
    opaque = secrets.token_urlsafe(32)
    expires = int(time.time()) + 600
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("DELETE FROM discord_oauth_states WHERE expires_at <= ?", (int(time.time()),))
        await db.execute(
            "INSERT INTO discord_oauth_states (state_hash, workspace_id, actor_id, draft_id, return_step, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_hash(opaque), principal.workspace_id, principal.user_id, draft_id, return_step, expires),
        )
        await db.commit()
    try:
        url = authorization_url(opaque)
    except DiscordAPIError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"authorization_url": url, "expires_in": 600}


@router.get("/integrations/discord/callback")
async def discord_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    guild_id: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if not state:
        raise HTTPException(400, "oauth_state_missing")
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
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
    frontend = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    if row["draft_id"]:
        path = f"/admin/tournaments/setup/{row['draft_id']}/{row['return_step']}"
    else:
        path = "/admin/hub"

    outcome = "failed"
    account_id = None
    if isinstance(error, str) and error:
        outcome = "cancelled"
    elif not code or not guild_id:
        outcome = "missing_context"
    else:
        try:
            token = await exchange_code(code)
            access_token = str(token.get("access_token") or "")
            if not access_token:
                raise DiscordAPIError("Discord did not return an access token")
            installer = await authorize_installer(access_token, guild_id)
            discovered = await discover_guild(guild_id)
            guild = discovered["guild"]
            workspace_id = str(row["workspace_id"])
            accounts = await list_integration_accounts(workspace_id)
            account = next((
                item for item in accounts
                if item.get("provider_type") == "discord"
                and str(item.get("external_account_id")) == str(guild_id)
            ), None)
            metadata = {
                "guild_id": str(guild_id),
                "guild_name": guild["name"],
                "installation_verified": True,
                "installed_by_id": str((installer.get("user") or {}).get("id") or ""),
                "granted_scopes": list(token.get("scope", "").split()),
                "permissions": str((installer.get("guild") or {}).get("permissions") or "0"),
            }
            if account:
                account_id = str(account["id"])
                account = await update_integration_account(
                    account_id, workspace_id=workspace_id,
                    external_account_id=str(guild_id), display_name=guild["name"], metadata=metadata,
                )
                if account.get("status") != "active":
                    await enable_integration_account(account_id, workspace_id=workspace_id)
            else:
                account = await create_integration_account(
                    workspace_id, "discord", str(guild_id), guild["name"], metadata=metadata,
                )
                account_id = str(account["id"])

            if row["draft_id"]:
                for _attempt in range(2):
                    draft = await get_draft(str(row["draft_id"]), workspace_id)
                    discord = dict(draft.get("discord_setup") or {})
                    discord.update({
                        "enabled": True,
                        "discord_account_id": account_id,
                        "guild_id": str(guild_id),
                        "guild_name": guild["name"],
                    })
                    try:
                        await patch_draft(
                            str(row["draft_id"]), workspace_id, str(row["actor_id"]),
                            section="discord_setup", value=discord,
                            expected_revision=int(draft["revision"]), current_step="discord",
                        )
                        break
                    except DraftRevisionConflict:
                        continue
            outcome = "authorized"
        except Exception:
            outcome = "failed"

    query = urlencode({
        "discord": outcome,
        **({"account_id": account_id} if account_id else {}),
        **({"settings": "connections"} if not row["draft_id"] else {}),
    })
    return RedirectResponse(f"{frontend}{path}?{query}", status_code=303)
