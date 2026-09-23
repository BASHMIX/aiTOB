"""The Discord runtime uses one platform-managed bot for every workspace."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_managed_bot_token_is_platform_owned(monkeypatch):
    from backend.bot import main

    monkeypatch.setenv("DISCORD_BOT_TOKEN", "platform-managed-token")
    monkeypatch.setenv("AITOB_DISCORD_ACCOUNT_ID", "legacy-account-must-be-ignored")
    monkeypatch.setenv("AITOB_DISCORD_WORKSPACE_ID", "legacy-workspace-must-be-ignored")
    monkeypatch.setattr(main, "init_db", AsyncMock(side_effect=AssertionError("token loading must not query tenant data")))

    token = main.load_managed_discord_token()

    assert token == "platform-managed-token"


@pytest.mark.asyncio
async def test_managed_bot_token_fails_closed_when_missing(monkeypatch):
    from backend.bot import main

    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_BOT_TOKEN"):
        main.load_managed_discord_token()


@pytest.mark.asyncio
async def test_organizer_command_requires_manage_server_permission(monkeypatch):
    from backend.bot import main

    resolver = AsyncMock()
    monkeypatch.setattr("backend.core.bot_routing.resolve_inbound_discord_route", resolver)
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=101),
        channel=SimpleNamespace(id=202),
        author=SimpleNamespace(guild_permissions=SimpleNamespace(manage_guild=False)),
    )

    with pytest.raises(RuntimeError, match="Manage Server"):
        await main._require_organizer_tournament_channel(ctx)
    resolver.assert_not_awaited()


@pytest.mark.asyncio
async def test_organizer_command_resolves_bound_tournament_channel(monkeypatch):
    from backend.bot import main

    expected = SimpleNamespace(workspace_id="workspace-a", tournament_id="event-a")
    resolver = AsyncMock(return_value=expected)
    monkeypatch.setattr("backend.core.bot_routing.resolve_inbound_discord_route", resolver)
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=101),
        channel=SimpleNamespace(id=202),
        author=SimpleNamespace(guild_permissions=SimpleNamespace(manage_guild=True)),
    )

    assert await main._require_organizer_tournament_channel(ctx) is expected
    resolver.assert_awaited_once_with("101", "202")


@pytest.mark.asyncio
async def test_managed_command_rejects_missing_workspace_scope():
    from backend.bot import main

    with pytest.raises(RuntimeError, match="explicit workspace"):
        await main.handle_ws_command("call_match set-a")


@pytest.mark.asyncio
async def test_verified_role_never_crosses_workspace_guild_boundary(monkeypatch):
    from backend.bot import main

    role_a = SimpleNamespace(name="Verified Player")
    role_b = SimpleNamespace(name="Verified Player")
    member_a = SimpleNamespace(
        roles=[], nick=None, add_roles=AsyncMock(), edit=AsyncMock(),
    )
    member_b = SimpleNamespace(
        roles=[], nick=None, add_roles=AsyncMock(), edit=AsyncMock(),
    )
    guild_a = SimpleNamespace(id=101, roles=[role_a], get_member=lambda _user_id: member_a)
    guild_b = SimpleNamespace(id=202, roles=[role_b], get_member=lambda _user_id: member_b)
    monkeypatch.setattr(main, "bot", SimpleNamespace(guilds=[guild_a, guild_b]))
    monkeypatch.setattr(main, "ws_add_bot_feed", AsyncMock())

    async def workspace_for_guild(guild_id):
        return {"101": "workspace-a", "202": "workspace-b"}[guild_id]

    monkeypatch.setattr("backend.core.bot_routing.resolve_workspace_for_guild", workspace_for_guild)

    await main.handle_ws_command(
        "apply_verified_role 7 ScopedTag", workspace_id="workspace-a",
    )

    member_a.add_roles.assert_awaited_once()
    member_a.edit.assert_awaited_once()
    member_b.add_roles.assert_not_awaited()
    member_b.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_verification_cannot_cross_workspace():
    from backend.core import database
    from backend.core.database import (
        create_pending_verification,
        get_pending_verification,
    )

    await database.init_db()
    await create_pending_verification(
        "discord-verification", "profile-a", "CODE-A", workspace_id="workspace-a",
    )
    assert await get_pending_verification("discord-verification", "workspace-a")
    assert await get_pending_verification("discord-verification", "workspace-b") is None
