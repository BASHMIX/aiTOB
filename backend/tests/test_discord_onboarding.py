import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from backend.api.routers import discord_oauth, integrations as integrations_api
from backend.api.routers.discord_oauth import _hash
from backend.core import database
from backend.core.discord_api import authorization_url
from backend.api.schemas import IntegrationAccountRequest, IntegrationCredentialRequest, IntegrationDestinationRequest


async def _seed(workspace_id="w", draft_id="d"):
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces(id,slug,name) VALUES (?,?,?)", (workspace_id, workspace_id, "Workspace"))
        await db.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES ('u','u@example.com','U','x')")
        await db.execute(
            "INSERT INTO tournament_setup_drafts(id,workspace_id,created_by,updated_by,answers_json) VALUES (?,?,?,?,?)",
            (draft_id, workspace_id, "u", "u", json.dumps({"discord_setup": {"enabled": True}})),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_discord_state_hash_is_one_way_and_expiry_scoped(postgres_repository_database):
    await _seed()
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO discord_oauth_states(state_hash,workspace_id,actor_id,draft_id,return_step,expires_at) VALUES (?,?,?,?,?,?)",
            (_hash("opaque"), "w", "u", "d", "discord", int(time.time()) + 60),
        )
        await db.commit()
        row = await (await db.execute("SELECT state_hash FROM discord_oauth_states")).fetchone()
    assert row[0] == _hash("opaque") and row[0] != "opaque"


def test_discord_install_url_uses_managed_application_and_required_scopes(monkeypatch):
    monkeypatch.setenv("DISCORD_CLIENT_ID", "client-1")
    monkeypatch.setenv("DISCORD_OAUTH_REDIRECT_URI", "https://aitob.example/api/integrations/discord/callback")
    query = parse_qs(urlparse(authorization_url("opaque-state")).query)
    assert query["client_id"] == ["client-1"]
    assert query["state"] == ["opaque-state"]
    assert set(query["scope"][0].split()) == {"identify", "guilds", "bot", "applications.commands"}
    assert int(query["permissions"][0]) > 0


@pytest.mark.asyncio
async def test_discord_callback_verifies_installer_and_updates_draft(postgres_repository_database, monkeypatch):
    await _seed()
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO discord_oauth_states(state_hash,workspace_id,actor_id,draft_id,return_step,expires_at) VALUES (?,?,?,?,?,?)",
            (_hash("opaque"), "w", "u", "d", "discord", int(time.time()) + 60),
        )
        await db.commit()

    async def exchange(_code):
        return {"access_token": "short-lived-user-token", "scope": "identify guilds bot applications.commands"}

    async def installer(_token, guild_id):
        return {"user": {"id": "installer-1"}, "guild": {"id": guild_id, "permissions": str(1 << 5)}}

    async def discover(guild_id):
        return {"guild": {"id": guild_id, "name": "Arena"}, "channels": [], "roles": []}

    monkeypatch.setattr(discord_oauth, "exchange_code", exchange)
    monkeypatch.setattr(discord_oauth, "authorize_installer", installer)
    monkeypatch.setattr(discord_oauth, "discover_guild", discover)
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://aitob.example")

    response = await discord_oauth.discord_callback(code="code", state="opaque", guild_id="guild-1")
    assert "discord=authorized" in response.headers["location"]

    core_integrations = __import__("backend.core.integrations", fromlist=["list_integration_accounts"])
    accounts = await core_integrations.list_integration_accounts("w")
    assert [(item["provider_type"], item["external_account_id"]) for item in accounts] == [("discord", "guild-1")]
    draft = await __import__("backend.core.tournament_setup", fromlist=["get_draft"]).get_draft("d", "w")
    assert draft["discord_setup"]["guild_id"] == "guild-1"
    assert draft["discord_setup"]["discord_account_id"] == accounts[0]["id"]


@pytest.mark.asyncio
async def test_discord_destination_and_test_message_require_ready_discovered_channel(postgres_repository_database, monkeypatch):
    await _seed()
    core_integrations = __import__("backend.core.integrations", fromlist=["create_integration_account"])
    account = await core_integrations.create_integration_account(
        "w", "discord", "guild-1", "Arena", metadata={"installation_verified": True},
    )
    principal = SimpleNamespace(workspace_id="w")

    async def discover(_guild_id):
        required = __import__("backend.core.discord_resources", fromlist=["REQUIRED_PERMISSIONS"]).REQUIRED_PERMISSIONS
        return {
            "guild": {"id": "guild-1", "name": "Arena"},
            "roles": [],
            "channels": [{"id": "channel-1", "name": "matches", "type": "0", "parent_id": None, "permissions": {name: True for name in required}}],
        }

    sent = []
    monkeypatch.setattr(integrations_api, "discover_guild", discover)
    monkeypatch.setattr(integrations_api, "send_test_message", lambda channel_id: _record(sent, channel_id))

    saved = await integrations_api.save_discord_destination(
        account["id"], {"channel_id": "channel-1", "destination_type": "match_call_channel"}, principal,
    )
    tested = await integrations_api.discord_test_message(account["id"], {"channel_id": "channel-1"}, principal)
    assert saved["configured"] is True
    assert tested["ok"] is True
    assert sent == ["channel-1"]


async def _record(values, value):
    values.append(value)
    return "message-1"


@pytest.mark.asyncio
async def test_discord_accounts_cannot_be_created_or_given_customer_tokens_through_generic_api(
    postgres_repository_database,
):
    await _seed()
    principal = SimpleNamespace(workspace_id="w")

    with pytest.raises(HTTPException, match="managed Discord installation"):
        await integrations_api.create_account(
            IntegrationAccountRequest(
                provider_type="discord",
                external_account_id="guild-manual",
                display_name="Manual guild",
            ),
            principal,
        )

    core_integrations = __import__("backend.core.integrations", fromlist=["create_integration_account"])
    account = await core_integrations.create_integration_account(
        "w", "discord", "guild-1", "Arena", metadata={"installation_verified": True},
    )
    with pytest.raises(HTTPException, match="customer bot tokens are not accepted"):
        await integrations_api.rotate_credential(
            account["id"],
            IntegrationCredentialRequest(secret_type="bot_token", secret="customer-token"),
            principal,
        )
    with pytest.raises(HTTPException, match="verified Discord destination endpoint"):
        await integrations_api.add_destination(
            account["id"],
            IntegrationDestinationRequest(
                destination_type="match_call_channel",
                external_id="channel-unverified",
                display_name="Unverified",
            ),
            principal,
        )
