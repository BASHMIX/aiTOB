import pytest
from psycopg.errors import UniqueViolation

from backend.core import database
from backend.core.bot_routing import (
    DiscordRouteMissing,
    resolve_inbound_discord_route,
    resolve_workspace_for_guild,
)
from backend.core.discord_resources import effective_permissions, permission_checks
from backend.core.integrations import add_integration_destination, create_integration_account


def test_effective_permissions_apply_overwrites():
    assert effective_permissions({"view_channel": True}, member_overwrites={"send_messages": True})["send_messages"] is True
    checks = permission_checks({"view_channel": False})
    assert any(item["reason_code"] == "missing_permission" for item in checks)


async def _seed_route(workspace_id: str, guild_id: str, channel_id: str, tournament_id: str):
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
            (workspace_id, workspace_id, workspace_id),
        )
        await db.execute(
            "INSERT INTO tournaments (slug, name, workspace_id) VALUES (?, ?, ?)",
            (tournament_id, tournament_id, workspace_id),
        )
        await db.commit()
    account = await create_integration_account(
        workspace_id, "discord", guild_id, f"Guild {guild_id}"
    )
    match_destination = await add_integration_destination(
        account["id"], "match_call_channel", channel_id, "Matches", workspace_id=workspace_id
    )
    escalation_destination = await add_integration_destination(
        account["id"], "escalation_channel", f"{channel_id}-staff", "Staff", workspace_id=workspace_id
    )
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            """INSERT INTO tournament_discord_bindings (
                   tournament_id, workspace_id, discord_account_id, guild_id,
                   match_destination_id, escalation_destination_id, status
               ) VALUES (?, ?, ?, ?, ?, ?, 'ready')""",
            (
                tournament_id,
                workspace_id,
                account["id"],
                guild_id,
                match_destination["id"],
                escalation_destination["id"],
            ),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_inbound_guild_and_channel_route_to_exact_workspace_and_tournament(postgres_repository_database):
    await _seed_route("workspace-a", "guild-a", "channel-a", "tournament-a")
    await _seed_route("workspace-b", "guild-b", "channel-b", "tournament-b")

    assert await resolve_workspace_for_guild("guild-a") == "workspace-a"
    route = await resolve_inbound_discord_route("guild-b", "channel-b")

    assert route.workspace_id == "workspace-b"
    assert route.tournament_id == "tournament-b"
    assert route.guild_id == "guild-b"
    assert route.channel_id == "channel-b"

    with pytest.raises(DiscordRouteMissing):
        await resolve_inbound_discord_route("guild-a", "channel-b")


@pytest.mark.asyncio
async def test_active_discord_guild_cannot_be_owned_by_two_workspaces(postgres_repository_database):
    await _seed_route("workspace-a", "shared-guild", "channel-a", "tournament-a")
    with pytest.raises(UniqueViolation):
        await _seed_route("workspace-b", "shared-guild", "channel-b", "tournament-b")
