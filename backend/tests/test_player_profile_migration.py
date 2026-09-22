"""PostgreSQL migration, tenant-isolation, deterministic-backfill, and ambiguous-legacy-review tests."""

from __future__ import annotations

import pytest
from backend.core import database
from backend.core import player_profiles


@pytest.mark.asyncio
async def test_player_profiles_schema_and_tenant_isolation(postgres_repository_database):
    """Verify player profile tables exist and enforce workspace isolation."""
    ws_a = "ws-isolation-a"
    ws_b = "ws-isolation-b"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?), (?, ?, ?) ON CONFLICT DO NOTHING",
                         (ws_a, "ws-a", "Workspace A", ws_b, "ws-b", "Workspace B"))
        await db.commit()

    # Create profile in WS A
    prof_a = await player_profiles.create_player_profile(
        workspace_id=ws_a,
        display_name="Player Alpha",
        prefix="TAG",
        country="JO",
        avatar_url="/static/avatars/alpha.png",
        discord_id="discord-alpha",
    )
    assert prof_a["id"]
    assert prof_a["display_name"] == "Player Alpha"

    # Verify WS B cannot read prof_a
    prof_b_view = await player_profiles.get_player_profile(prof_a["id"], ws_b)
    assert prof_b_view is None

    # Verify list in WS B is empty
    list_b = await player_profiles.list_player_profiles(ws_b)
    assert len(list_b) == 0

    list_a = await player_profiles.list_player_profiles(ws_a)
    assert len(list_a) == 1
    assert list_a[0]["id"] == prof_a["id"]


@pytest.mark.asyncio
async def test_deterministic_backfill_and_ambiguous_legacy_review(postgres_repository_database):
    """Verify deterministic migration from players and links to player profiles and scoped overrides,

    and verify that ambiguous legacy overrides are flagged for review without heuristic guessing.
    """
    ws = "ws-migration-test"
    raw_data = """{
        "events": [{
            "id": "sf6-ev-1",
            "name": "SF6 Event",
            "entrants": {
                "nodes": [{"id": "entrant-det-1", "name": "Player One"}]
            }
        }]
    }"""

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                         (ws, "ws-mig", "Migration WS"))
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("tourney-mig-1", "Tourney One", "SF6 Event", "sf6-ev-1", "SF6", raw_data, ws),
        )
        await db.commit()

    # 1. Seed player with Start.gg and CFN
    await database.create_or_update_player(
        discord_id="discord-mig-1",
        gamertag="GamerTag1",
        team="PREFIX1",
        country="JO",
        avatar_path="/static/avatars/gt1.png",
        startgg_id="sgg-12345",
        cfn_id="CFN-12345",
        workspace_id=ws,
    )

    # 2. Link entrant-det-1 to this player
    await database.link_tournament_entrant(
        tournament_slug="tourney-mig-1",
        entrant_id="entrant-det-1",
        discord_id="discord-mig-1",
        workspace_id=ws,
    )

    # 3. Save deterministically attributable legacy override
    await database.save_player_override(
        entrant_id="entrant-det-1",
        data={
            "name": "Custom Name 1",
            "country": "JO",
            "avatar_url": "/static/avatars/custom.png",
            "character_id": "2282",
            "character_name": "Juri",
            "character_image_url": "https://cdn.example/juri.png",
        },
        workspace_id=ws,
    )

    # 4. Save an ambiguous legacy override (no matching tournament link)
    await database.save_player_override(
        entrant_id="entrant-ambiguous-99",
        data={
            "name": "Orphan Override",
            "country": "US",
        },
        workspace_id=ws,
    )

    # Run backfill
    stats = await database.backfill_player_profiles_and_overrides(workspace_id=ws)
    assert stats["profiles_created"] >= 1
    assert stats["provider_identities_created"] >= 1
    assert stats["game_profiles_created"] >= 1
    assert stats["overrides_converted"] == 1
    assert stats["overrides_marked_review"] == 1

    # Verify profile created
    prof = await player_profiles.get_player_profile_by_discord_id("discord-mig-1", ws)
    assert prof is not None
    assert prof["display_name"] == "GamerTag1"
    assert prof["prefix"] == "PREFIX1"
    assert prof["avatar_url"] == "/static/avatars/gt1.png"

    # Verify provider identity created
    sgg_ident = await player_profiles.find_profile_by_provider_identity(ws, "startgg", "sgg-12345")
    assert sgg_ident is not None
    assert sgg_ident["id"] == prof["id"]

    # Verify game profile created
    gp = await player_profiles.get_player_game_profile(ws, prof["id"], "SF6")
    assert gp is not None
    assert gp["in_game_id"] == "CFN-12345"

    # Verify scoped override created for deterministic entrant
    scoped_ov = await player_profiles.get_tournament_entrant_override(
        workspace_id=ws,
        provider="startgg",
        tournament_slug="tourney-mig-1",
        event_id="sf6-ev-1",
        entrant_id="entrant-det-1",
    )
    assert scoped_ov is not None
    assert scoped_ov["display_name"] == "Custom Name 1"
    assert scoped_ov["character_name"] == "Juri"

    # Verify ambiguous override was marked for review, not converted
    ambiguous_scoped = await player_profiles.get_tournament_entrant_override(
        workspace_id=ws,
        provider="startgg",
        tournament_slug="tourney-mig-1",
        event_id="sf6-ev-1",
        entrant_id="entrant-ambiguous-99",
    )
    assert ambiguous_scoped is None

    ambiguous_legacy = await database.get_player_override("entrant-ambiguous-99", ws)
    assert ambiguous_legacy is not None
    assert ambiguous_legacy["requires_review"] is True
