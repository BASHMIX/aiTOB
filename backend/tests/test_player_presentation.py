"""Resolver precedence, provenance, and no-provider-call tests for player presentation."""

from __future__ import annotations

import pytest
from backend.core.contracts.player_presentation import (
    EntrantPresentationRequest,
    EntrantScope,
)
from backend.core.player_presentation import (
    resolve_entrant_presentation,
    resolve_presentation_v1,
)
from backend.core import database
from backend.core import player_profiles


def test_pure_resolver_precedence_and_provenance():
    """Verify override → profile → provider → placeholder field-by-field precedence and provenance."""
    scope = EntrantScope(
        provider="startgg",
        tournament_slug="slug-test",
        event_id="ev-1",
        entrant_id="ent-1",
    )

    # 1. Full override present -> all fields have source 'entrant_override'
    res_override = resolve_presentation_v1(
        scope,
        override={
            "display_name": "Override Name",
            "prefix": "OV",
            "country": "JO",
            "avatar_url": "/ov/avatar.png",
            "character_id": "101",
            "character_name": "Ryu",
            "character_image_url": "/img/ryu.png",
        },
        profile={
            "display_name": "Profile Name",
            "prefix": "PROF",
            "country": "US",
            "avatar_url": "/prof/avatar.png",
        },
        provider_snapshot={
            "name": "Provider Name",
            "prefix": "PROV",
            "country": "FR",
            "avatar_url": "/prov/avatar.png",
        },
        linked=True,
        player_profile_id="prof-1",
    )
    assert res_override.presentation.display_name.value == "Override Name"
    assert res_override.presentation.display_name.source == "entrant_override"
    assert res_override.presentation.prefix.value == "OV"
    assert res_override.presentation.prefix.source == "entrant_override"
    assert res_override.presentation.country.value == "JO"
    assert res_override.presentation.country.source == "entrant_override"
    assert res_override.presentation.avatar_url.value == "/ov/avatar.png"
    assert res_override.presentation.avatar_url.source == "entrant_override"
    assert res_override.presentation.character.value.name == "Ryu"
    assert res_override.presentation.character.source == "entrant_override"
    assert res_override.linked is True
    assert res_override.player_profile_id == "prof-1"

    # 2. No override, linked profile present -> fields fall through to player_profile
    res_profile = resolve_presentation_v1(
        scope,
        override=None,
        profile={
            "id": "prof-2",
            "display_name": "Profile Name",
            "prefix": "PROF",
            "country": "US",
            "avatar_url": "/prof/avatar.png",
        },
        game_profile={
            "character_id": "202",
            "character_name": "Chun-Li",
            "character_image_url": "/img/chunli.png",
        },
        provider_snapshot={
            "name": "Provider Name",
            "prefix": "PROV",
            "country": "FR",
            "avatar_url": "/prov/avatar.png",
        },
        linked=True,
    )
    assert res_profile.presentation.display_name.value == "Profile Name"
    assert res_profile.presentation.display_name.source == "player_profile"
    assert res_profile.presentation.avatar_url.value == "/prof/avatar.png"
    assert res_profile.presentation.avatar_url.source == "player_profile"
    assert res_profile.presentation.character.value.name == "Chun-Li"
    assert res_profile.presentation.character.source == "player_profile"

    # 3. Unlinked -> provider fallback
    res_provider = resolve_presentation_v1(
        scope,
        override=None,
        profile=None,
        provider_snapshot={
            "name": "Provider Tag",
            "prefix": "PROV",
            "country": "IQ",
            "avatar_url": "https://prov.example/pic.png",
        },
        linked=False,
    )
    assert res_provider.presentation.display_name.value == "Provider Tag"
    assert res_provider.presentation.display_name.source == "provider_snapshot"
    assert res_provider.presentation.avatar_url.value == "https://prov.example/pic.png"
    assert res_provider.presentation.avatar_url.source == "provider_snapshot"
    assert res_provider.presentation.character.source == "placeholder"
    assert res_provider.linked is False
    assert res_provider.player_profile_id is None

    # 4. Completely empty -> placeholder
    res_empty = resolve_presentation_v1(scope, override=None, profile=None, provider_snapshot=None, linked=False)
    assert res_empty.presentation.display_name.value == ""
    assert res_empty.presentation.display_name.source == "placeholder"
    assert res_empty.presentation.avatar_url.value == "/static/player_placeholder.jpg"
    assert res_empty.presentation.avatar_url.source == "placeholder"


@pytest.mark.asyncio
async def test_resolve_entrant_presentation_uses_only_local_data_with_no_provider_calls(
    postgres_repository_database, monkeypatch
):
    """Verify resolve_entrant_presentation resolves strictly from local tables without external calls."""
    ws = "ws-pres-local"
    raw_data = """{
        "events": [{
            "id": "sf6-ev-local",
            "name": "Local SF6",
            "entrants": {
                "nodes": [{
                    "id": "entrant-loc-1",
                    "name": "Local Player",
                    "participants": [{"user": {"images": [{"type": "profile", "url": "https://cdn.example/loc.png"}]}}]
                }]
            }
        }]
    }"""

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                         (ws, "ws-loc", "Local WS"))
        await db.execute(
            """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("tourney-loc", "Local Tourney", "Local SF6", "sf6-ev-local", "SF6", raw_data, ws),
        )
        await db.commit()

    # Create player profile and link entrant
    prof = await player_profiles.create_player_profile(
        workspace_id=ws,
        display_name="Approved GamerTag",
        avatar_url="/static/avatars/approved_loc.png",
        discord_id="discord-loc-1",
    )
    await database.create_or_update_player(
        discord_id="discord-loc-1",
        gamertag="Approved GamerTag",
        avatar_path="/static/avatars/approved_loc.png",
        workspace_id=ws,
    )
    await database.link_tournament_entrant(
        tournament_slug="tourney-loc",
        entrant_id="entrant-loc-1",
        discord_id="discord-loc-1",
        workspace_id=ws,
    )

    # Set game profile default character
    gp = await player_profiles.set_player_game_profile(ws, prof["id"], "SF6", in_game_id="LOC-CFN")
    await player_profiles.set_player_character_default(
        workspace_id=ws,
        player_game_profile_id=gp["id"],
        character_id="2275",
        character_name="Dhalsim",
        character_image_url="https://catalog.example/dhalsim.png",
    )

    # Guard against network or provider calls
    def network_guard(*args, **kwargs):
        raise AssertionError("No network or provider call allowed during presentation resolution")

    monkeypatch.setattr("httpx.AsyncClient.get", network_guard, raising=False)
    monkeypatch.setattr("httpx.AsyncClient.post", network_guard, raising=False)

    req = EntrantPresentationRequest(
        provider="startgg",
        tournament_slug="tourney-loc",
        event_id="sf6-ev-local",
        entrant_id="entrant-loc-1",
    )
    result = await resolve_entrant_presentation(ws, req)

    assert result.version == "v1"
    assert result.linked is True
    assert result.player_profile_id == prof["id"]
    assert result.presentation.display_name.value == "Approved GamerTag"
    assert result.presentation.display_name.source == "player_profile"
    assert result.presentation.avatar_url.value == "/static/avatars/approved_loc.png"
    assert result.presentation.avatar_url.source == "player_profile"
    assert result.presentation.character.value.name == "Dhalsim"
    assert result.presentation.character.source == "player_profile"
