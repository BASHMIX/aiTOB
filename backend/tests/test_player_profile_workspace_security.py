"""Cross-workspace authorization and concurrent profile/override update tests."""

from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core import player_profiles
from backend.core.workspace_auth import SessionPrincipal


def _make_principal(workspace_id: str, role: str = "owner") -> SessionPrincipal:
    return SessionPrincipal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        role=role,
        session_id=f"session-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_cross_workspace_game_preference_isolation(postgres_repository_database, monkeypatch):
    """Verify game preferences and character defaults are strictly isolated by workspace."""
    ws_1 = "ws-sec-1"
    ws_2 = "ws-sec-2"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_1, "ws-sec-1", "Security WS 1"))
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_2, "ws-sec-2", "Security WS 2"))
        await db.commit()

    # Create profile in WS 1
    prof_1 = await player_profiles.create_player_profile(
        workspace_id=ws_1,
        display_name="Player 1 in WS1",
    )
    p1_id = prof_1["id"]

    gp_1 = await player_profiles.set_player_game_profile(
        workspace_id=ws_1,
        player_profile_id=p1_id,
        game_id="SF6",
        in_game_name="P1SF6",
    )
    gp1_id = gp_1["id"]

    await player_profiles.set_player_character_default(
        workspace_id=ws_1,
        player_game_profile_id=gp1_id,
        character_id="juri",
        character_name="Juri",
    )

    # 1. WS 2 principal tries to list game profiles for p1_id -> 404 Not Found
    principal_2 = _make_principal(ws_2)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal_2))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "session-ws2")

        res_list_gp = await client.get(f"/api/player-profiles/{p1_id}/game-profiles")
        assert res_list_gp.status_code == 404

        # WS 2 principal tries to add a game profile to WS 1 profile -> 404 Not Found
        res_add_gp = await client.post(
            f"/api/player-profiles/{p1_id}/game-profiles",
            json={"game_id": "T8", "in_game_name": "Intruder"},
        )
        assert res_add_gp.status_code == 404

        # WS 2 principal tries to add a character default to WS 1 game profile -> 404 Not Found
        res_add_cd = await client.post(
            f"/api/player-profiles/{p1_id}/game-profiles/{gp1_id}/character-defaults",
            json={"character_id": "jin", "character_name": "Jin"},
        )
        assert res_add_cd.status_code == 404


@pytest.mark.asyncio
async def test_concurrent_tournament_entrant_override_updates(postgres_repository_database):
    """Verify concurrent updates to the same entrant override handle row-locking cleanly

    without deadlocks or duplicate entries.
    """
    workspace_id = "ws-concurrent-updates"
    slug = "conctourney"
    event_id = "ev-conc-1"
    entrant_id = "ent-conc-1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (workspace_id, "conc-ws", "Concurrent WS"))
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (slug, "Concurrent Tourney", "Event 1", event_id, "SF6", "{}", workspace_id),
        )
        await db.commit()

    # Launch 10 simultaneous updates to the same entrant override
    async def update_entrant(index: int):
        return await player_profiles.set_tournament_entrant_override(
            workspace_id=workspace_id,
            provider="startgg",
            tournament_slug=slug,
            event_id=event_id,
            entrant_id=entrant_id,
            data={
                "display_name": f"Runner {index}",
                "prefix": f"P{index}",
                "character_name": f"Char {index}",
            },
            updated_by=f"user-{index}",
        )

    results = await asyncio.gather(*[update_entrant(i) for i in range(10)])
    assert len(results) == 10

    # Ensure only exactly 1 override record exists in the database for this entrant
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            """SELECT COUNT(*), MIN(display_name), MAX(display_name) FROM tournament_entrant_overrides
               WHERE workspace_id = ? AND tournament_slug = ? AND entrant_id = ?""",
            (workspace_id, slug, entrant_id),
        ) as cur:
            row = await cur.fetchone()
            assert row[0] == 1, f"Expected exactly 1 override record, found {row[0]}"
            # The final display name should be one of Runner 0..9
            assert row[1].startswith("Runner ")


@pytest.mark.asyncio
async def test_concurrent_profile_updates(postgres_repository_database):
    """Verify concurrent updates to a player profile complete without lost state or race conditions."""
    workspace_id = "ws-concurrent-profile"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (workspace_id, "cprof-ws", "Conc Profile WS"))
        await db.commit()

    prof = await player_profiles.create_player_profile(
        workspace_id=workspace_id,
        display_name="Initial Name",
        country="US",
    )
    profile_id = prof["id"]

    async def update_profile(index: int):
        return await player_profiles.update_player_profile(
            profile_id=profile_id,
            workspace_id=workspace_id,
            data={
                "display_name": f"Concurrent Name {index}",
                "notes": f"Note {index}",
            },
        )

    results = await asyncio.gather(*[update_profile(i) for i in range(8)])
    assert len(results) == 8

    # Verify final profile state is intact
    final_prof = await player_profiles.get_player_profile(profile_id, workspace_id)
    assert final_prof is not None
    assert final_prof["country"] == "US"  # Preserved
    assert final_prof["display_name"].startswith("Concurrent Name ")
