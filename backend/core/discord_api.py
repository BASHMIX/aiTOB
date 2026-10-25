"""Discord REST boundary for the platform-managed aiTOB application."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.core.discord_resources import permissions_from_bitfield


API_BASE = "https://discord.com/api/v10"
AUTHORIZE_URL = "https://discord.com/oauth2/authorize"

# View/send/embed/history, manage nicknames/roles/threads, create public
# threads, and send inside threads. No Administrator permission is requested.
BOT_PERMISSION_BITS = sum(1 << bit for bit in (10, 11, 14, 16, 27, 28, 34, 35, 38))


class DiscordAPIError(RuntimeError):
    """Safe Discord failure that never contains tokens or upstream bodies."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise DiscordAPIError(f"{name} is not configured")
    return value


def oauth_redirect_uri() -> str:
    configured = os.getenv("DISCORD_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/api/integrations/discord/callback"


def authorization_url(state: str) -> str:
    query = urlencode({
        "client_id": _required_env("DISCORD_CLIENT_ID"),
        "redirect_uri": oauth_redirect_uri(),
        "response_type": "code",
        "scope": "identify guilds bot applications.commands",
        "permissions": str(BOT_PERMISSION_BITS),
        "state": state,
        "integration_type": "0",
    })
    return f"{os.getenv('DISCORD_OAUTH_AUTHORIZE_URL', AUTHORIZE_URL)}?{query}"


async def _request(method: str, path: str, *, token: str, bearer: bool = False, **kwargs: Any) -> Any:
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"{'Bearer' if bearer else 'Bot'} {token}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.request(method, f"{API_BASE}{path}", headers=headers, **kwargs)
    if response.status_code < 200 or response.status_code >= 300:
        raise DiscordAPIError(f"Discord request failed ({response.status_code})")
    return response.json() if response.content else None


async def exchange_code(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{API_BASE}/oauth2/token",
            data={
                "client_id": _required_env("DISCORD_CLIENT_ID"),
                "client_secret": _required_env("DISCORD_CLIENT_SECRET"),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": oauth_redirect_uri(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code != 200:
        raise DiscordAPIError(f"Discord authorization failed ({response.status_code})")
    return response.json()


async def authorize_installer(access_token: str, guild_id: str) -> dict[str, Any]:
    user = await _request("GET", "/users/@me", token=access_token, bearer=True)
    guilds = await _request("GET", "/users/@me/guilds", token=access_token, bearer=True)
    guild = next((item for item in guilds if str(item.get("id")) == str(guild_id)), None)
    if not guild:
        raise DiscordAPIError("The authorized Discord user cannot access the selected server")
    permissions = int(guild.get("permissions") or 0)
    if not (permissions & (1 << 3) or permissions & (1 << 5)):
        raise DiscordAPIError("Manage Server permission is required")
    return {"user": user, "guild": guild}


def _effective_channel_bits(
    guild_id: str,
    member_id: str,
    member_role_ids: list[str],
    roles: list[dict[str, Any]],
    channel: dict[str, Any],
) -> int:
    role_bits = {str(role.get("id")): int(role.get("permissions") or 0) for role in roles}
    bits = role_bits.get(str(guild_id), 0)
    for role_id in member_role_ids:
        bits |= role_bits.get(str(role_id), 0)
    if bits & (1 << 3):
        return (1 << 53) - 1
    overwrites = channel.get("permission_overwrites") or []
    everyone = next((item for item in overwrites if str(item.get("id")) == str(guild_id)), None)
    if everyone:
        bits &= ~int(everyone.get("deny") or 0)
        bits |= int(everyone.get("allow") or 0)
    role_overwrites = [item for item in overwrites if str(item.get("id")) in member_role_ids]
    denied = 0
    allowed = 0
    for item in role_overwrites:
        denied |= int(item.get("deny") or 0)
        allowed |= int(item.get("allow") or 0)
    bits = (bits & ~denied) | allowed
    member = next((item for item in overwrites if str(item.get("id")) == str(member_id)), None)
    if member:
        bits &= ~int(member.get("deny") or 0)
        bits |= int(member.get("allow") or 0)
    return bits


async def discover_guild(guild_id: str) -> dict[str, Any]:
    token = _required_env("DISCORD_BOT_TOKEN")
    bot_user = await _request("GET", "/users/@me", token=token)
    member_id = str(bot_user.get("id") or "")
    if not member_id:
        raise DiscordAPIError("Discord did not return the managed bot identity")
    guild = await _request("GET", f"/guilds/{guild_id}", token=token)
    channels = await _request("GET", f"/guilds/{guild_id}/channels", token=token)
    roles = await _request("GET", f"/guilds/{guild_id}/roles", token=token)
    # Discord has no /guilds/{guild}/members/@me bot endpoint. Resolve the
    # managed application's bot identity once, then request that guild member
    # explicitly so channel permission calculation uses the real role set.
    member = await _request("GET", f"/guilds/{guild_id}/members/{member_id}", token=token)
    member_roles = [str(value) for value in member.get("roles") or []]
    safe_channels = []
    for channel in channels:
        # Forum/media channels require creating a post rather than sending a
        # normal message, so they are not valid tournament destinations yet.
        if int(channel.get("type", -1)) not in {0, 5}:
            continue
        bits = _effective_channel_bits(str(guild_id), member_id, member_roles, roles, channel)
        safe_channels.append({
            "id": str(channel.get("id")),
            "name": str(channel.get("name") or "Unnamed channel"),
            "type": str(channel.get("type")),
            "parent_id": str(channel.get("parent_id")) if channel.get("parent_id") else None,
            "permissions": permissions_from_bitfield(bits),
        })
    return {
        "guild": {"id": str(guild.get("id")), "name": str(guild.get("name") or "Discord server")},
        "channels": safe_channels,
        "roles": [{"id": str(role.get("id")), "name": str(role.get("name") or "Role")} for role in roles],
    }


async def send_test_message(channel_id: str) -> str:
    token = _required_env("DISCORD_BOT_TOKEN")
    message = await _request(
        "POST",
        f"/channels/{channel_id}/messages",
        token=token,
        json={"content": "✅ aiTOB is connected. Tournament messages can be delivered to this channel."},
    )
    return str(message.get("id") or "")


async def send_channel_embed(channel_id: str, embed: dict) -> str:
    token = _required_env("DISCORD_BOT_TOKEN")
    message = await _request(
        "POST",
        f"/channels/{channel_id}/messages",
        token=token,
        json={"embeds": [embed]},
    )
    return str(message.get("id") or "")


__all__ = [
    "BOT_PERMISSION_BITS", "DiscordAPIError", "authorization_url", "oauth_redirect_uri",
    "exchange_code", "authorize_installer", "discover_guild", "send_test_message", "send_channel_embed",
]
