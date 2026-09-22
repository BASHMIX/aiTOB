"""API integration tests for player profiles archive CRUD, game preferences, and workspace isolation."""

from __future__ import annotations
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core.workspace_auth import SessionPrincipal


def _make_principal(workspace_id: str, role: str = "owner") -> SessionPrincipal:
    return SessionPrincipal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        role=role,
        session_id=f"session-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_player_profile_api_crud_and_game_preferences(postgres_repository_database, monkeypatch):
    """Test full CRUD lifecycle of player profiles and their game preferences via the REST API."""
    workspace_id = "ws-profile-api-1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "prof-api-ws", "Profile API Workspace"),
        )
        await db.commit()

    principal = _make_principal(workspace_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-session")

        # 1. Initially empty
        res = await client.get("/api/player-profiles")
        assert res.status_code == 200
        assert res.json() == {"profiles": []}

        # 2. Create profile
        create_payload = {
            "display_name": "Daigo Umehara",
            "prefix": "BST",
            "country": "JP",
            "avatar_url": "https://cdn.example/daigo.png",
            "discord_id": "daigo#0001",
        }
        res_create = await client.post("/api/player-profiles", json=create_payload)
        assert res_create.status_code == 201, res_create.text
        created = res_create.json()
        profile_id = created["id"]
        assert created["display_name"] == "Daigo Umehara"
        assert created["prefix"] == "BST"
        assert created["country"] == "JP"

        # 3. Create a second profile to test listing and search
        await client.post(
            "/api/player-profiles",
            json={"display_name": "Tokido", "prefix": "ROHTO", "country": "JP"},
        )

        res_list = await client.get("/api/player-profiles", params={"query": "Daigo"})
        assert res_list.status_code == 200
        profiles = res_list.json()["profiles"]
        assert len(profiles) == 1
        assert profiles[0]["display_name"] == "Daigo Umehara"

        # 4. Add Game Profile
        gp_payload = {
            "game_id": "SF6",
            "in_game_name": "TheBeastSF6",
            "in_game_id": "BEAST-1234",
        }
        res_gp = await client.post(f"/api/player-profiles/{profile_id}/game-profiles", json=gp_payload)
        assert res_gp.status_code == 201
        gp_data = res_gp.json()
        game_profile_id = gp_data["id"]
        assert gp_data["game_id"] == "SF6"

        # 5. Add Character Default to Game Profile
        char_payload = {
            "character_id": "ken",
            "character_name": "Ken Masters",
            "character_image_url": "https://cdn.example/ken_sf6.png",
            "is_primary": True,
        }
        res_cd = await client.post(
            f"/api/player-profiles/{profile_id}/game-profiles/{game_profile_id}/character-defaults",
            json=char_payload,
        )
        assert res_cd.status_code == 201
        cd_data = res_cd.json()
        assert cd_data["character_id"] == "ken"
        assert cd_data["is_primary"] is True

        # 6. Fetch Profile Detail
        res_detail = await client.get(f"/api/player-profiles/{profile_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["id"] == profile_id
        assert detail["display_name"] == "Daigo Umehara"
        assert len(detail["game_profiles"]) == 1
        assert detail["game_profiles"][0]["game_id"] == "SF6"
        assert len(detail["game_profiles"][0]["character_defaults"]) == 1
        assert detail["game_profiles"][0]["character_defaults"][0]["character_name"] == "Ken Masters"

        # 7. Update Profile (PATCH)
        res_patch = await client.patch(
            f"/api/player-profiles/{profile_id}",
            json={"display_name": "The Beast Daigo", "prefix": "RED BULL", "notes": "Archive note"},
        )
        assert res_patch.status_code == 200
        patched = res_patch.json()
        assert patched["display_name"] == "The Beast Daigo"
        assert patched["prefix"] == "RED BULL"
        assert patched["country"] == "JP"  # Unchanged
        assert patched["notes"] == "Archive note"

        # 8. Delete Profile
        res_del = await client.delete(f"/api/player-profiles/{profile_id}")
        assert res_del.status_code == 200
        assert res_del.json()["ok"] is True

        # Confirm 404 after deletion
        res_after = await client.get(f"/api/player-profiles/{profile_id}")
        assert res_after.status_code == 404


@pytest.mark.asyncio
async def test_player_profile_api_tenant_isolation(postgres_repository_database, monkeypatch):
    """Verify player profile CRUD operations enforce strict workspace boundaries."""
    ws_1 = "ws-tenant-p1"
    ws_2 = "ws-tenant-p2"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_1, "ws-1", "Workspace 1"))
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_2, "ws-2", "Workspace 2"))
        await db.commit()

    principal_1 = _make_principal(ws_1)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal_1))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "session-1")

        # Create profile in WS 1
        res_create = await client.post(
            "/api/player-profiles",
            json={"display_name": "Player in WS 1"},
        )
        assert res_create.status_code == 201
        p1_id = res_create.json()["id"]

    # Now authenticate as WS 2
    principal_2 = _make_principal(ws_2)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal_2))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "session-2")

        # WS 2 list should be empty
        res_list = await client.get("/api/player-profiles")
        assert res_list.status_code == 200
        assert res_list.json() == {"profiles": []}

        # WS 2 cannot get WS 1 profile
        res_get = await client.get(f"/api/player-profiles/{p1_id}")
        assert res_get.status_code == 404

        # WS 2 cannot patch WS 1 profile
        res_patch = await client.patch(
            f"/api/player-profiles/{p1_id}",
            json={"display_name": "Hacked Name"},
        )
        assert res_patch.status_code == 404

        # WS 2 cannot delete WS 1 profile
        res_delete = await client.delete(f"/api/player-profiles/{p1_id}")
        assert res_delete.status_code == 404
