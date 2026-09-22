"""Tests for scoped tournament entrant overrides: event isolation, reset, catalog validation, and workspace boundaries."""

from __future__ import annotations
import json
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
async def test_scoped_override_event_isolation_and_reset(postgres_repository_database):
    """Verify that entrant overrides in two different events/tournaments remain isolated

    and do not leak to each other or alter the reusable player profile.
    Resetting one override restores profile presentation without touching the other event.
    """
    workspace_id = "ws-scoped-isolation-1"
    raw_tourney_a = json.dumps({
        "events": [{
            "id": "event-sf6",
            "name": "Street Fighter 6",
            "entrants": {
                "nodes": [{
                    "id": "entrant-a1",
                    "name": "MultiGamePro",
                    "participants": [{"user": {"images": [{"type": "profile", "url": "https://cdn.example/p_a.png"}]}}]
                }]
            }
        }]
    })
    raw_tourney_b = json.dumps({
        "events": [{
            "id": "event-t8",
            "name": "Tekken 8",
            "entrants": {
                "nodes": [{
                    "id": "entrant-b1",
                    "name": "MultiGamePro",
                    "participants": [{"user": {"images": [{"type": "profile", "url": "https://cdn.example/p_b.png"}]}}]
                }]
            }
        }]
    })

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "scoped-ws", "Scoped Workspace"),
        )
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("tourney-sf6", "SF6 Cup", "Street Fighter 6", "event-sf6", "SF6", raw_tourney_a, workspace_id),
        )
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("tourney-t8", "T8 Clash", "Tekken 8", "event-t8", "T8", raw_tourney_b, workspace_id),
        )
        await db.commit()

    # Create one reusable profile for the player
    profile = await database.create_or_update_player(
        discord_id="discord-pro",
        gamertag="PRO | ReusableProfile",
        prefix="PRO",
        country="JO",
        cfn_id="PRO-CFN",
        avatar_path="/static/avatars/reusable_pro.png",
        workspace_id=workspace_id,
    )

    # Link player to entrant in tourney-sf6
    await database.link_tournament_entrant(
        tournament_slug="tourney-sf6",
        entrant_id="entrant-a1",
        discord_id="discord-pro",
        workspace_id=workspace_id,
    )

    # Link player to entrant in tourney-t8
    await database.link_tournament_entrant(
        tournament_slug="tourney-t8",
        entrant_id="entrant-b1",
        discord_id="discord-pro",
        workspace_id=workspace_id,
    )

    # Set scoped override for event-sf6: Ryu
    await player_profiles.set_tournament_entrant_override(
        workspace_id=workspace_id,
        provider="startgg",
        tournament_slug="tourney-sf6",
        event_id="event-sf6",
        entrant_id="entrant-a1",
        data={
            "display_name": "Ryu Master",
            "character_id": "sf6-ryu",
            "character_name": "Ryu",
            "character_image_url": "https://cdn.example/ryu.png",
        },
    )

    # Set scoped override for event-t8: Jin
    await player_profiles.set_tournament_entrant_override(
        workspace_id=workspace_id,
        provider="startgg",
        tournament_slug="tourney-t8",
        event_id="event-t8",
        entrant_id="entrant-b1",
        data={
            "display_name": "Jin Kazama",
            "character_id": "t8-jin",
            "character_name": "Jin",
            "character_image_url": "https://cdn.example/jin.png",
        },
    )

    # Read scoped override for tourney-sf6
    ov_a = await player_profiles.get_tournament_entrant_override(
        workspace_id, "startgg", "tourney-sf6", "event-sf6", "entrant-a1"
    )
    assert ov_a is not None
    assert ov_a["display_name"] == "Ryu Master"
    assert ov_a["character_name"] == "Ryu"

    # Read scoped override for tourney-t8
    ov_b = await player_profiles.get_tournament_entrant_override(
        workspace_id, "startgg", "tourney-t8", "event-t8", "entrant-b1"
    )
    assert ov_b is not None
    assert ov_b["display_name"] == "Jin Kazama"
    assert ov_b["character_name"] == "Jin"

    # Verify reusable player profile remains unchanged
    p = await database.get_player("discord-pro", workspace_id)
    assert p["gamer_tag"] == "PRO | ReusableProfile"
    assert p["avatar_path"] == "/static/avatars/reusable_pro.png"

    # Reset (delete) tourney-sf6 override
    deleted = await player_profiles.delete_tournament_entrant_override(
        workspace_id, "startgg", "tourney-sf6", "event-sf6", "entrant-a1"
    )
    assert deleted is True

    # tourney-sf6 override is now gone
    assert await player_profiles.get_tournament_entrant_override(
        workspace_id, "startgg", "tourney-sf6", "event-sf6", "entrant-a1"
    ) is None

    # tourney-t8 override is still intact!
    ov_b_after = await player_profiles.get_tournament_entrant_override(
        workspace_id, "startgg", "tourney-t8", "event-t8", "entrant-b1"
    )
    assert ov_b_after is not None
    assert ov_b_after["character_name"] == "Jin"


@pytest.mark.asyncio
async def test_scoped_override_catalog_validation(postgres_repository_database, monkeypatch):
    """Verify that setting a character override validates against the tournament/event catalog."""
    workspace_id = "ws-catalog-val"
    raw_tourney = json.dumps({
        "events": [{
            "id": "event-catalog-1",
            "name": "Catalog Tournament",
            "entrants": {
                "nodes": [{
                    "id": "entrant-cat-1",
                    "name": "CatalogGamer",
                    "participants": [{"user": {"images": []}}]
                }]
            }
        }]
    })

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "cat-ws", "Catalog Workspace"),
        )
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, provider_type, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, 'startgg', ?)""",
            ("cat-tourney", "Catalog Cup", "Street Fighter 6", "event-catalog-1", "SF6", raw_tourney, workspace_id),
        )
        await db.commit()

    # Store game metadata with valid character catalog
    await database.set_tournament_game_metadata(
        slug="cat-tourney",
        event_id="event-catalog-1",
        metadata={
            "event_id": "event-catalog-1",
            "characters": [
                {"id": "sf6-luke", "name": "Luke", "image_url": "https://cdn.example/luke.png"},
                {"id": "sf6-jamie", "name": "Jamie", "image_url": "https://cdn.example/jamie.png"},
            ]
        },
        workspace_id=workspace_id,
    )

    principal = _make_principal(workspace_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-token")

        # 1. Selecting an invalid character not in catalog returns 409 Conflict
        bad_res = await client.patch("/api/players/overrides/entrant-cat-1", json={
            "character_id": "invalid-char-999",
            "character": "Nonexistent Char",
            "tournament_slug": "cat-tourney",
            "event_id": "event-catalog-1",
        })
        assert bad_res.status_code == 409
        msg = bad_res.json().get("message") or bad_res.json().get("detail") or ""
        assert "catalog" in msg.lower()

        # 2. Selecting a valid character succeeds
        good_res = await client.patch("/api/players/overrides/entrant-cat-1", json={
            "character_id": "sf6-luke",
            "character": "Luke",
            "tournament_slug": "cat-tourney",
            "event_id": "event-catalog-1",
        })
        assert good_res.status_code == 200
        assert good_res.json().get("ok") is True

        # 3. Read back scoped override
        scoped = await player_profiles.get_tournament_entrant_override(
            workspace_id, "startgg", "cat-tourney", "event-catalog-1", "entrant-cat-1"
        )
        assert scoped is not None
        assert scoped["character_id"] == "sf6-luke"
        # Scoped participant edits must not also mutate the legacy OBS projection.
        assert await database.get_player_override("entrant-cat-1", workspace_id) is None
        assert scoped["character_name"] == "Luke"
        assert scoped["character_image_url"] == "https://cdn.example/luke.png"
