"""Provider OAuth must upgrade migrated accounts without breaking references."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api.routers import provider_oauth
from backend.api.routers.settings import api_patch_env
from backend.api.schemas import PatchEnvRequest
from backend.core import database, integrations
from backend.core.storage import dbapi


async def _workspace(workspace_id: str = "oauth-workspace") -> None:
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
            (workspace_id, workspace_id, "OAuth Workspace"),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_startgg_oauth_upgrades_single_legacy_account_in_place(monkeypatch):
    monkeypatch.setenv("AITOB_INTEGRATION_MASTER_KEY", "7lXNrOpw2HnqGYiRkqzGN70KGyxoDpcQ0H3jDXiVlvc=")
    await _workspace()
    legacy = await integrations.create_integration_account(
        "oauth-workspace", "startgg", "legacy", "Migrated Start.gg",
    )
    await database.upsert_tournament(
        "tournament/oauth-upgrade", "OAuth upgrade", "", "", "", "{}",
        provider_type="startgg", provider_tournament_id="123",
        provider_account_id=legacy["id"], workspace_id="oauth-workspace",
    )

    async def identity(_token: str) -> dict:
        return {"id": 987, "name": "Organizer", "slug": "organizer", "player": {"gamerTag": "FNC"}}

    monkeypatch.setattr(provider_oauth, "_startgg_identity", identity)
    account_id = await provider_oauth._upsert_oauth_account(
        "startgg", "oauth-workspace", {"access_token": "new-access-token", "refresh_token": "new-refresh-token"},
    )

    accounts = await integrations.list_integration_accounts("oauth-workspace")
    tournament = await database.get_tournament("tournament/oauth-upgrade")
    assert account_id == legacy["id"]
    assert [(item["id"], item["external_account_id"], item["display_name"]) for item in accounts] == [
        (legacy["id"], "987", "FNC"),
    ]
    assert tournament["provider_account_id"] == legacy["id"]
    assert await integrations.get_integration_secret(legacy["id"], "access_token") == "new-access-token"
    assert await integrations.get_integration_secret(legacy["id"], "refresh_token") == "new-refresh-token"


@pytest.mark.asyncio
async def test_challonge_oauth_upgrades_single_legacy_account_in_place(monkeypatch):
    monkeypatch.setenv("AITOB_INTEGRATION_MASTER_KEY", "7lXNrOpw2HnqGYiRkqzGN70KGyxoDpcQ0H3jDXiVlvc=")
    await _workspace("challonge-oauth-workspace")
    legacy = await integrations.create_integration_account(
        "challonge-oauth-workspace", "challonge", "legacy", "Migrated Challonge",
    )

    async def identity(_token: str) -> dict:
        return {"id": "challonge-owner-1", "name": "FNC Challonge"}

    monkeypatch.setattr(provider_oauth, "_challonge_identity", identity)
    account_id = await provider_oauth._upsert_oauth_account(
        "challonge", "challonge-oauth-workspace", {"access_token": "challonge-access-token"},
    )

    accounts = await integrations.list_integration_accounts("challonge-oauth-workspace")
    assert account_id == legacy["id"]
    assert [(item["id"], item["external_account_id"], item["display_name"]) for item in accounts] == [
        (legacy["id"], "challonge-owner-1", "FNC Challonge"),
    ]


@pytest.mark.asyncio
async def test_global_environment_rejects_retired_startgg_credentials():
    with pytest.raises(HTTPException, match="account-scoped") as caught:
        await api_patch_env(PatchEnvRequest(
            STARTGG_API_TOKEN="retired-token",
            STARTGG_CLIENT_ID="retired-client",
            STARTGG_CLIENT_SECRET="retired-secret",
        ))

    assert caught.value.status_code == 409
