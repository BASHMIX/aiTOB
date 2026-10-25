"""Workspace-scoped Discord bot experience and customization endpoints."""

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.auth import require_permission
from backend.core.database import get_workspace_bot_settings, upsert_workspace_bot_settings
from backend.core.workspace_auth import SessionPrincipal


router = APIRouter(prefix="/workspace/bot-settings", tags=["bot-settings"])


class PatchWorkspaceBotSettingsRequest(BaseModel):
    custom_rules_markdown: str | None = Field(default=None, max_length=4000)
    welcome_message: str | None = Field(default=None, max_length=2000)
    faq_help_text: str | None = Field(default=None, max_length=2000)
    enable_avatar_uploads: bool | None = None
    enable_match_threads: bool | None = None
    enable_rules_command: bool | None = None
    response_mode: Literal["direct_template", "llm_assistant", "disabled"] | None = None
    language_mode: Literal["auto", "ar", "en", "both"] | None = None


@router.get("", summary="Get workspace bot customization settings")
async def get_bot_settings(
    principal: SessionPrincipal = Depends(require_permission("settings.manage")),
):
    """Retrieve the bot customization profile for the authenticated workspace."""
    settings = await get_workspace_bot_settings(principal.workspace_id)
    return {"settings": settings}


@router.patch("", summary="Update workspace bot customization settings")
async def update_bot_settings(
    body: PatchWorkspaceBotSettingsRequest,
    principal: SessionPrincipal = Depends(require_permission("settings.manage")),
):
    """Update message templates, feature toggles, and response modes for the workspace's bot."""
    updates = body.model_dump(exclude_none=True)
    updated = await upsert_workspace_bot_settings(principal.workspace_id, **updates)
    return {"settings": updated, "message": "Bot settings updated successfully"}


@router.post("/preview-test", summary="Send a test embed to the workspace Discord channel")
async def send_preview_test(
    principal: SessionPrincipal = Depends(require_permission("settings.manage")),
):
    """Deliver a test embed to the connected tournament channel to preview formatting."""
    from backend.core.integrations import list_integration_accounts, list_integration_destinations
    from backend.core.discord_api import send_channel_embed, DiscordAPIError

    accounts = await list_integration_accounts(principal.workspace_id)
    discord_account = next(
        (a for a in accounts if a.get("provider_type") == "discord" and a.get("status") == "active"),
        None,
    )
    if not discord_account:
        return {
            "ok": False,
            "message": "No active Discord server connected. Please connect Discord in Settings → Connections first.",
        }

    destinations = await list_integration_destinations(discord_account["id"], workspace_id=principal.workspace_id)
    match_dest = next((d for d in destinations if d.get("destination_type") == "match_call_channel"), None)
    if not match_dest or not match_dest.get("destination_external_id"):
        return {
            "ok": False,
            "message": "No match-call channel destination configured. Please configure it in Settings → Connections.",
        }

    channel_id = match_dest["destination_external_id"]
    settings = await get_workspace_bot_settings(principal.workspace_id)

    rules_text = settings.get("custom_rules_markdown") or "Standard tournament rules apply."
    welcome_text = settings.get("welcome_message") or "Welcome to the tournament! Use /register to join."

    embed = {
        "title": "📋 [aiTOB Preview] Tournament Experience",
        "description": f"**Welcome Message:**\n{welcome_text}\n\n**Rules & Instructions (/rules):**\n{rules_text}",
        "color": 0xF59E0B,  # Gold
        "fields": [
            {
                "name": "⚙️ Configured Features",
                "value": (
                    f"• Rules Command: `{'Enabled' if settings.get('enable_rules_command') else 'Disabled'}`\n"
                    f"• Avatar Uploads: `{'Enabled' if settings.get('enable_avatar_uploads') else 'Disabled'}`\n"
                    f"• Match Threads: `{'Enabled' if settings.get('enable_match_threads') else 'Disabled'}`\n"
                    f"• Response Mode: `{settings.get('response_mode', 'direct_template')}`"
                ),
                "inline": False,
            }
        ],
        "footer": {"text": "aiTOB Bot Experience Preview · bashtech.xyz"},
    }

    try:
        msg_id = await send_channel_embed(channel_id, embed)
        return {
            "ok": True,
            "message": f"Preview embed delivered successfully to Discord channel <#{channel_id}> (Message ID: {msg_id}).",
        }
    except DiscordAPIError as exc:
        return {
            "ok": False,
            "message": f"Failed to send Discord message: {str(exc)}",
        }

