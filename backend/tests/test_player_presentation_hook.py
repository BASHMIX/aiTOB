"""Tests for the versioned v1 player presentation hook contract, authorization, and zero-side-effects."""

from __future__ import annotations
import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core.workspace_auth import SessionPrincipal
from backend.core import player_profiles


def _make_principal(workspace_id: str, role: str = "owner") -> SessionPrincipal:
    return SessionPrincipal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        role=role,
        session_id=f"session-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_v1_presentation_hook_contract_and_provenance(postgres_repository_database, monkeypatch):
    """Verify POST and GET /api/player-profiles/presentation/v1 satisfy the contract and provenance rules."""
    workspace_id = "ws-hook-contract-1"
    event_id = "sf6-hook-ev-1"
    entrant_id = "entrant-hook-1"
    slug = "hooktourney"

    raw_data = json.dumps({
        "events": [{
            "id": event_id,
            "name": "SF6 Hook Event",
            "entrants": {
                "nodes": [{
                    "id": entrant_id,
                    "name": "ProviderHookTag",
                    "prefix": "PHT",
                    "participants": [{
                        "user": {
                            "location": {"country": "FR"},
                            "images": [{"type": "profile", "url": "https://cdn.example/hook_provider.png"}],
                        }
                    }]
                }]
            }
        }]
    })

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "hook-ws", "Hook Test Workspace"),
        )
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (slug, "Hook Tourney", "SF6 Hook Event", event_id, "SF6", raw_data, workspace_id),
        )
        await db.commit()

    principal = _make_principal(workspace_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-session")

        # 1. Unlinked entrant - fallback to provider_snapshot
        req_payload = {
            "provider": "startgg",
            "tournament_slug": slug,
            "event_id": event_id,
            "entrant_id": entrant_id,
        }
        res = await client.post("/api/player-profiles/presentation/v1", json=req_payload)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["version"] == "v1"
        assert data["linked"] is False
        assert data["player_profile_id"] is None
        assert data["entrant"]["entrant_id"] == entrant_id
        assert data["presentation"]["display_name"]["value"] == "ProviderHookTag"
        assert data["presentation"]["display_name"]["source"] == "provider_snapshot"
        assert data["presentation"]["prefix"]["value"] == "PHT"
        assert data["presentation"]["prefix"]["source"] == "provider_snapshot"
        assert data["presentation"]["country"]["value"] == "FR"
        assert data["presentation"]["country"]["source"] == "provider_snapshot"
        assert data["presentation"]["avatar_url"]["value"] == "https://cdn.example/hook_provider.png"
        assert data["presentation"]["avatar_url"]["source"] == "provider_snapshot"
        assert data["presentation"]["character"]["source"] == "placeholder"

        # Also test GET query parameter endpoint
        res_get = await client.get(
            "/api/player-profiles/presentation/v1",
            params={
                "provider": "startgg",
                "tournament_slug": slug,
                "event_id": event_id,
                "entrant_id": entrant_id,
            },
        )
        assert res_get.status_code == 200
        assert res_get.json() == data

        # 2. Link entrant to reusable profile and configure game preference
        created_profile = await player_profiles.create_player_profile(
            workspace_id=workspace_id,
            display_name="Linked Pro Gamer",
            prefix="PRO",
            country="DE",
            avatar_url="/static/avatars/pro_avatar.png",
            discord_id="discord-pro-1",
        )
        assert created_profile is not None
        profile_id = created_profile["id"]

        await database.create_or_update_player(
            discord_id="discord-pro-1",
            workspace_id=workspace_id,
            gamer_tag="Linked Pro Gamer",
        )

        gp = await player_profiles.set_player_game_profile(
            workspace_id=workspace_id,
            player_profile_id=profile_id,
            game_id="SF6",
            in_game_name="ProGamerSF6",
        )
        await player_profiles.set_player_character_default(
            workspace_id=workspace_id,
            player_game_profile_id=gp["id"],
            character_id="ryu",
            character_name="Ryu",
            character_image_url="https://cdn.example/ryu.png",
            is_primary=True,
        )

        await database.link_tournament_entrant(
            tournament_slug=slug,
            entrant_id=entrant_id,
            discord_id="discord-pro-1",
            workspace_id=workspace_id,
        )

        res2 = await client.post("/api/player-profiles/presentation/v1", json=req_payload)
        assert res2.status_code == 200
        data2 = res2.json()

        assert data2["linked"] is True
        assert data2["player_profile_id"] == profile_id
        assert data2["presentation"]["display_name"]["value"] == "Linked Pro Gamer"
        assert data2["presentation"]["display_name"]["source"] == "player_profile"
        assert data2["presentation"]["prefix"]["value"] == "PRO"
        assert data2["presentation"]["prefix"]["source"] == "player_profile"
        assert data2["presentation"]["country"]["value"] == "DE"
        assert data2["presentation"]["country"]["source"] == "player_profile"
        assert data2["presentation"]["avatar_url"]["value"] == "/static/avatars/pro_avatar.png"
        assert data2["presentation"]["avatar_url"]["source"] == "player_profile"
        assert data2["presentation"]["character"]["value"]["name"] == "Ryu"
        assert data2["presentation"]["character"]["source"] == "player_profile"

        # 3. Apply scoped tournament override: should take top precedence
        await player_profiles.set_tournament_entrant_override(
            workspace_id=workspace_id,
            provider="startgg",
            tournament_slug=slug,
            event_id=event_id,
            entrant_id=entrant_id,
            data={
                "display_name": "Tournament Custom Name",
                "character_name": "Ken",
                "character_id": "ken",
                "character_image_url": "https://cdn.example/ken.png",
            },
        )

        res3 = await client.post("/api/player-profiles/presentation/v1", json=req_payload)
        assert res3.status_code == 200
        data3 = res3.json()

        assert data3["presentation"]["display_name"]["value"] == "Tournament Custom Name"
        assert data3["presentation"]["display_name"]["source"] == "entrant_override"
        # Non-overridden fields retain player_profile source
        assert data3["presentation"]["prefix"]["value"] == "PRO"
        assert data3["presentation"]["prefix"]["source"] == "player_profile"
        assert data3["presentation"]["avatar_url"]["value"] == "/static/avatars/pro_avatar.png"
        assert data3["presentation"]["avatar_url"]["source"] == "player_profile"
        # Character was overridden
        assert data3["presentation"]["character"]["value"]["name"] == "Ken"
        assert data3["presentation"]["character"]["source"] == "entrant_override"


@pytest.mark.asyncio
async def test_v1_presentation_hook_authorization_and_tenant_isolation(postgres_repository_database, monkeypatch):
    """Verify unauthorized callers are rejected and cross-workspace data is not exposed."""
    ws_a = "ws-hook-tenant-a"
    ws_b = "ws-hook-tenant-b"
    event_id = "ev-tenant-1"
    entrant_id = "entrant-tenant-1"
    slug = "isolated-tourney"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_a, "ws-a", "Workspace A"))
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_b, "ws-b", "Workspace B"))
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (slug, "Tourney A", "Event 1", event_id, "SF6", "{}", ws_a),
        )
        await db.commit()

    # Create profile and link in Workspace A
    await database.create_or_update_player(
        discord_id="discord-secret-a",
        gamertag="Secret Gamer A",
        workspace_id=ws_a,
    )
    await database.link_tournament_entrant(
        tournament_slug=slug,
        entrant_id=entrant_id,
        discord_id="discord-secret-a",
        workspace_id=ws_a,
    )

    req_payload = {
        "provider": "startgg",
        "tournament_slug": slug,
        "event_id": event_id,
        "entrant_id": entrant_id,
    }

    # 1. Unauthenticated request rejected
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_unauth = await client.post("/api/player-profiles/presentation/v1", json=req_payload)
        assert res_unauth.status_code == 401

    # 2. Authenticated as Workspace B: Cannot see Workspace A's linked profile
    principal_b = _make_principal(ws_b)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal_b))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-session-b")
        res_b = await client.post("/api/player-profiles/presentation/v1", json=req_payload)
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["linked"] is False
        assert data_b["player_profile_id"] is None
        assert data_b["presentation"]["display_name"]["source"] == "placeholder"


@pytest.mark.asyncio
async def test_v1_presentation_hook_zero_side_effects(postgres_repository_database, monkeypatch):
    """Verify calling the v1 hook performs strictly read-only resolution with zero side-effects."""
    workspace_id = "ws-hook-zero-effect"
    event_id = "ev-zero-1"
    entrant_id = "entrant-zero-1"
    slug = "zerotourney"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (workspace_id, "ws-z", "Workspace Z"))
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (slug, "Zero Tourney", "Event 1", event_id, "SF6", "{}", workspace_id),
        )
        await db.execute(
            """INSERT INTO stations (id, public_id, name, workspace_id)
               VALUES (?, ?, ?, ?)""",
            ("st-1", "pub-st-1", "Station 1", workspace_id),
        )
        await db.execute(
            """INSERT INTO active_matches (
                set_id, station_id, status, p1_name, p2_name, p1_entrant_id, p2_entrant_id, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("m-100", "st-1", "in_progress", "P1 Zero", "P2 Zero", "ent-1", "ent-2", workspace_id),
        )
        await db.commit()

    principal = _make_principal(workspace_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    # Read state before hook invocation
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT id, name, public_id FROM stations WHERE workspace_id = ?", (workspace_id,)) as cur:
            stations_before = await cur.fetchall()
        async with db.execute("SELECT set_id, status FROM active_matches WHERE workspace_id = ?", (workspace_id,)) as cur:
            matches_before = await cur.fetchall()
        async with db.execute("SELECT COUNT(*) FROM player_profiles WHERE workspace_id = ?", (workspace_id,)) as cur:
            profiles_count_before = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tournament_entrant_overrides WHERE workspace_id = ?", (workspace_id,)) as cur:
            overrides_count_before = (await cur.fetchone())[0]

    # Call v1 presentation hook
    req_payload = {
        "provider": "startgg",
        "tournament_slug": slug,
        "event_id": event_id,
        "entrant_id": entrant_id,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-session")
        res = await client.post("/api/player-profiles/presentation/v1", json=req_payload)
        assert res.status_code == 200

    # Read state after hook invocation - assert exact equality
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT id, name, public_id FROM stations WHERE workspace_id = ?", (workspace_id,)) as cur:
            stations_after = await cur.fetchall()
        async with db.execute("SELECT set_id, status FROM active_matches WHERE workspace_id = ?", (workspace_id,)) as cur:
            matches_after = await cur.fetchall()
        async with db.execute("SELECT COUNT(*) FROM player_profiles WHERE workspace_id = ?", (workspace_id,)) as cur:
            profiles_count_after = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tournament_entrant_overrides WHERE workspace_id = ?", (workspace_id,)) as cur:
            overrides_count_after = (await cur.fetchone())[0]

    assert stations_before == stations_after
    assert matches_before == matches_after
    assert profiles_count_before == profiles_count_after == 0
    assert overrides_count_before == overrides_count_after == 0
