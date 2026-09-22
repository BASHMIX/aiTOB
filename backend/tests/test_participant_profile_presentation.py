"""API-level tests for participant presentation resolution and profile precedence."""

from __future__ import annotations
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core import player_profiles
from backend.core.workspace_auth import SessionPrincipal


def _make_principal(workspace_id: str) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        role="owner",
        session_id=f"session-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_participant_presentation_api_precedence_and_link(postgres_repository_database, monkeypatch):
    """Verify GET /api/players/presentation returns resolved presentation with profile precedence

    for linked entrants, provider fallback for unlinked entrants, and override precedence.
    """
    workspace_id = "ws-pres-api-1"
    raw_data = """{
        "events": [{
            "id": "sf6-event-1",
            "name": "Street Fighter 6",
            "entrants": {
                "nodes": [
                    {
                        "id": "entrant-1",
                        "name": "ProviderGamer1",
                        "prefix": "PRV",
                        "participants": [{"user": {"images": [{"type": "profile", "url": "https://cdn.example/p1_provider.png"}]}}]
                    },
                    {
                        "id": "entrant-2",
                        "name": "ProviderGamer2",
                        "prefix": "PRV2",
                        "participants": [{"user": {"images": [{"type": "profile", "url": "https://cdn.example/p2_provider.png"}]}}]
                    }
                ]
            }
        }]
    }"""
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "pres-api-ws", "Presentation API Workspace"),
        )
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("precontourney", "Presentation Cup", "Street Fighter 6", "sf6-event-1", "SF6", raw_data, workspace_id),
        )
        await db.commit()

    # Seed reusable profile for entrant-1
    await database.create_or_update_player(
        discord_id="discord-p1",
        gamertag="Approved P1",
        prefix="APP",
        country="JO",
        cfn_id="CFN-P1",
        avatar_path="/static/avatars/p1_approved.png",
        workspace_id=workspace_id,
    )
    profile = await player_profiles.create_player_profile(
        workspace_id=workspace_id,
        display_name="Approved P1",
        prefix="APP",
        country="JO",
        avatar_url="/static/avatars/p1_approved.png",
        discord_id="discord-p1",
    )
    game_profile = await player_profiles.set_player_game_profile(
        workspace_id, profile["id"], "SF6", in_game_id="CFN-P1"
    )
    await player_profiles.set_player_character_default(
        workspace_id, game_profile["id"], "sf6-ryu", "Ryu",
        "https://cdn.example/ryu-default.png",
    )

    # Link entrant-1 to player
    await database.link_tournament_entrant(
        tournament_slug="precontourney",
        entrant_id="entrant-1",
        discord_id="discord-p1",
        workspace_id=workspace_id,
    )

    principal = _make_principal(workspace_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-token")

        # 1. Fetch presentations for precontourney
        res = await client.get("/api/players/presentation", params={"tournament_slug": "precontourney"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert len(data) == 2

        by_entrant = {item["entrant"]["entrant_id"]: item for item in data}

        # Entrant 1 is linked: should have profile avatar and display name precedence
        p1 = by_entrant["entrant-1"]
        assert p1["linked"] is True
        assert p1["presentation"]["display_name"]["value"] == "Approved P1"
        assert p1["presentation"]["display_name"]["source"] == "player_profile"
        assert p1["presentation"]["avatar_url"]["value"] == "/static/avatars/p1_approved.png"
        assert p1["presentation"]["avatar_url"]["source"] == "player_profile"
        assert p1["presentation"]["character"]["value"]["name"] == "Ryu"
        assert p1["presentation"]["character"]["source"] == "player_profile"

        # Entrant 2 is unlinked: should fall back to provider snapshot
        p2 = by_entrant["entrant-2"]
        assert p2["linked"] is False
        assert p2["presentation"]["display_name"]["value"] == "ProviderGamer2"
        assert p2["presentation"]["display_name"]["source"] == "provider_snapshot"
        assert p2["presentation"]["avatar_url"]["value"] == "https://cdn.example/p2_provider.png"
        assert p2["presentation"]["avatar_url"]["source"] == "provider_snapshot"

        # 2. Add an override for entrant-1 (e.g. custom avatar and character)
        await database.save_player_override(
            entrant_id="entrant-1",
            data={
                "name": "Overridden Entrant 1",
                "avatar_url": "https://cdn.example/custom_entrant_1.png",
                "character": "Ryu",
                "character_name": "Ryu",
                "character_id": "101",
                "character_image_url": "https://cdn.example/ryu.png",
            },
            workspace_id=workspace_id,
        )

        res_after = await client.get("/api/players/presentation", params={"tournament_slug": "precontourney"})
        assert res_after.status_code == 200
        by_entrant_after = {item["entrant"]["entrant_id"]: item for item in res_after.json()}

        p1_after = by_entrant_after["entrant-1"]
        assert p1_after["presentation"]["display_name"]["value"] == "Overridden Entrant 1"
        assert p1_after["presentation"]["display_name"]["source"] == "entrant_override"
        assert p1_after["presentation"]["avatar_url"]["value"] == "https://cdn.example/custom_entrant_1.png"
        assert p1_after["presentation"]["avatar_url"]["source"] == "entrant_override"
        assert p1_after["presentation"]["character"]["value"]["name"] == "Ryu"
        assert p1_after["presentation"]["character"]["source"] == "entrant_override"

        # 3. Path-based presentation route works identically
        res_slug = await client.get("/api/players/presentation/precontourney")
        assert res_slug.status_code == 200
        assert len(res_slug.json()) == 2

        # 4. Cross-workspace isolation: another workspace cannot access precontourney
        other_principal = _make_principal("ws-other-presentation")
        monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=other_principal))
        res_other = await client.get("/api/players/presentation", params={"tournament_slug": "precontourney"})
        assert res_other.status_code == 200
        assert res_other.json() == []
