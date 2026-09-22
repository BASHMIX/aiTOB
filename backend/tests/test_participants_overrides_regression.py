"""Regression tests capturing the baseline participant review, overrides, and FNCeSports case."""

from __future__ import annotations
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from backend.api.main import app
from backend.core import database
from backend.core.workspace_auth import SessionPrincipal


def _make_principal(workspace_id: str) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        role="owner",
        session_id=f"session-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_fncesports_participant_override_regression_baseline(postgres_repository_database):
    """Capture the baseline behavior where linked profile avatar and character selection

    are not unified in a single presentation projection, and legacy overrides lack
    character persistence columns.
    """
    workspace_id = "ws-fnc-1"
    raw_data = """{
        "events": [{
            "id": "sf6-event-1",
            "name": "Street Fighter 6",
            "entrants": {
                "nodes": [{
                    "id": "entrant-fnc-1",
                    "name": "FNCeSports",
                    "participants": [{"user": {"images": [{"type": "profile", "url": "https://cdn.example/provider_fnc.png"}]}}]
                }]
            }
        }]
    }"""
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "fnc-ws", "FNC Workspace"),
        )
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("fnctourney", "FNC Championship", "Street Fighter 6", "sf6-event-1", "SF6", raw_data, workspace_id),
        )
        await db.commit()

    # Seed reusable player profile (aiTOB player)
    await database.create_or_update_player(
        discord_id="discord-fnc",
        gamertag="FNC | FNCeSports",
        prefix="FNC",
        country="JO",
        cfn_id="FNC-CFN",
        avatar_path="/static/avatars/fnc_approved.png",
        workspace_id=workspace_id,
    )

    # Link entrant to player
    link = await database.link_tournament_entrant(
        tournament_slug="fnctourney",
        entrant_id="entrant-fnc-1",
        discord_id="discord-fnc",
        workspace_id=workspace_id,
    )
    assert link["discord_id"] == "discord-fnc"
    assert link["avatar_path"] == "/static/avatars/fnc_approved.png"

    # Verify link is retrievable
    links = await database.get_tournament_player_links("fnctourney", workspace_id)
    assert "entrant-fnc-1" in links
    assert links["entrant-fnc-1"]["discord_id"] == "discord-fnc"
    assert links["entrant-fnc-1"]["avatar_path"] == "/static/avatars/fnc_approved.png"

    # In baseline, get_all_player_overrides does NOT populate the entrant from the link
    overrides = await database.get_all_player_overrides(workspace_id)
    assert "entrant-fnc-1" not in overrides

    # If we save a legacy override, save_player_override inserts into player_overrides
    await database.save_player_override(
        entrant_id="entrant-fnc-1",
        data={
            "name": "FNCeSports Custom",
            "country": "JO",
            "avatar_url": "https://cdn.example/override_avatar.png",
        },
        workspace_id=workspace_id,
    )

    # Legacy override read baseline
    fetched_override = await database.get_player_override("entrant-fnc-1", workspace_id)
    assert fetched_override is not None

    all_overrides = await database.get_all_player_overrides(workspace_id)
    assert isinstance(all_overrides, dict)


@pytest.mark.asyncio
async def test_participant_overrides_api_response_shape(postgres_repository_database, monkeypatch):
    """Capture API response shape for /api/players/overrides and /api/players/links."""
    workspace_id = "ws-fnc-api"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "fnc-api-ws", "FNC API Workspace"),
        )
        await db.execute(
            "INSERT INTO tournaments (slug, name, raw_data, workspace_id) VALUES (?, ?, ?, ?)",
            ("slug-test-1", "Test Tournament", "{}", workspace_id),
        )
        await db.commit()

    # Save an override
    await database.save_player_override(
        entrant_id="entrant-99",
        data={"name": "Override Player", "country": "JO", "avatar_url": "/managed/avatar.png"},
        workspace_id=workspace_id,
    )

    principal = _make_principal(workspace_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-token")

        # GET /api/players/overrides
        response = await client.get("/api/players/overrides")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

        # GET /api/players/links
        links_resp = await client.get("/api/players/links", params={"tournament_slug": "slug-test-1"})
        assert links_resp.status_code == 200
        assert "links" in links_resp.json()
