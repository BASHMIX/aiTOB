"""Authorized Discord member identity operations."""
from __future__ import annotations

from typing import Any, Protocol


class DiscordMemberAdapter(Protocol):
    async def fetch_member(self, guild_id: str, member_id: str) -> dict[str, Any] | None: ...
    async def edit_nickname(self, guild_id: str, member_id: str, nickname: str) -> None: ...


def validate_snowflake(value: str) -> str:
    text = str(value or "").strip()
    if not text.isdigit() or not 17 <= len(text) <= 20:
        raise ValueError("invalid_discord_id")
    return text


async def set_server_nickname(adapter: DiscordMemberAdapter, *, guild_id: str, member_id: str, gamertag: str, bot_user_id: str | None = None) -> dict[str, Any]:
    guild = validate_snowflake(guild_id)
    member = validate_snowflake(member_id)
    if bot_user_id and member == validate_snowflake(bot_user_id):
        raise ValueError("bot_member_not_allowed")
    if not str(gamertag or "").strip() or len(str(gamertag)) > 32:
        raise ValueError("invalid_nickname")
    found = await adapter.fetch_member(guild, member)
    if not found:
        raise ValueError("member_not_in_guild")
    if found.get("bot"):
        raise ValueError("bot_member_not_allowed")
    if not found.get("can_manage_nickname", True):
        raise ValueError("missing_permission")
    await adapter.edit_nickname(guild, member, str(gamertag).strip())
    return {"guild_id": guild, "discord_user_id": member, "nickname": str(gamertag).strip(), "state": "linked"}


__all__ = ["DiscordMemberAdapter", "validate_snowflake", "set_server_nickname"]
