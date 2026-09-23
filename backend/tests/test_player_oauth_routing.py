"""Regression coverage for workspace-safe player OAuth through the shared bot."""

from urllib.parse import parse_qs, urlparse

import pytest

from backend.api.routers import auth
from backend.core import database
from backend.core.player_oauth import (
    consume_player_oauth_state,
    create_player_oauth_state,
    inspect_player_oauth_state,
)


@pytest.mark.asyncio
async def test_player_oauth_state_is_workspace_scoped_and_single_use(postgres_repository_database):
    state = await create_player_oauth_state("workspace-a", "discord-a", ttl_seconds=60)

    assert await inspect_player_oauth_state(state) == {
        "workspace_id": "workspace-a",
        "actor_id": "discord-a",
    }
    assert await consume_player_oauth_state(state) == {
        "workspace_id": "workspace-a",
        "actor_id": "discord-a",
    }
    assert await consume_player_oauth_state(state) is None


@pytest.mark.asyncio
async def test_player_oauth_callback_updates_and_queues_only_state_workspace(
    postgres_repository_database, monkeypatch,
):
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
            ("workspace-a", "workspace-a", "Workspace A"),
        )
        await db.commit()
    await database.create_or_update_player(
        "discord-a", workspace_id="workspace-a", registration_step="startgg_linked",
    )
    state = await create_player_oauth_state("workspace-a", "discord-a", ttl_seconds=60)

    async def exchange(_code, _redirect_uri):
        return {"access_token": "provider-token"}

    async def current_user(_token):
        return {"id": "sgg-a", "player": {"gamerTag": "Scoped Player"}}

    monkeypatch.setattr(auth, "_exchange_code_for_token", exchange)
    monkeypatch.setattr(auth, "_fetch_current_user", current_user)

    response = await auth.callback("oauth-code", state)

    assert response.status_code == 200
    player = await database.get_player("discord-a", "workspace-a")
    assert player["startgg_id"] == "sgg-a"
    commands = await database.get_pending_hub_commands("workspace-a")
    assert [row["command_text"] for row in commands] == [
        "apply_verified_role discord-a Scoped Player"
    ]
    assert await consume_player_oauth_state(state) is None


@pytest.mark.asyncio
async def test_player_oauth_login_preserves_opaque_state(monkeypatch, postgres_repository_database):
    state = await create_player_oauth_state("workspace-a", "discord-a", ttl_seconds=60)

    async def secret(key, default=None):
        return "client-a" if key == "STARTGG_CLIENT_ID" else default

    monkeypatch.setattr(auth, "_resolve_secret", secret)
    response = await auth.login(state)
    query = parse_qs(urlparse(response.headers["location"]).query)

    assert query["state"] == [state]
    assert query["client_id"] == ["client-a"]
    assert await inspect_player_oauth_state(state) is not None
