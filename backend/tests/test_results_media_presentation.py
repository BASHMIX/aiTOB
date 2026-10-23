"""Tests for event-scoped character override, explicit profile promotion, and version immutability."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core import player_profiles
from backend.core.player_presentation import resolve_entrant_presentation
from backend.core.contracts.player_presentation import EntrantScope
from backend.core.results_media_repository import create_result_version, get_result_version_by_id
from backend.core.workspace_auth import SessionPrincipal


def _make_principal(workspace_id: str, role: str = "owner", user_id: str = "user-test") -> SessionPrincipal:
    return SessionPrincipal(
        user_id=user_id,
        workspace_id=workspace_id,
        role=role,
        session_id=f"sess-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_event_character_override_and_explicit_promotion(postgres_repository_database, monkeypatch):
    """Verify event-only override isolation, version immutability, and explicit audited promotion."""
    ws = "ws-pres-test"
    user_id = "user-pres-1"
    slug = "t-pres-1"
    event_id = "ev-pres-1"
    game_id = "tekken8"
    entrant_id = "ent-pres-1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (ws, "pres-ws", "Presentation WS"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING",
            (user_id, "pres@example.com", "presuser"),
        )
        await db.execute(
            "INSERT INTO tournaments (workspace_id, slug, name, provider_type, game) VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (ws, slug, "Tekken Cup", "startgg", game_id),
        )
        await db.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner') ON CONFLICT DO NOTHING",
            (ws, user_id),
        )
        await db.commit()

    # 1. Create a Player Archive profile with default character "Jin"
    profile = await player_profiles.create_player_profile(
        workspace_id=ws,
        display_name="FighterOne",
        country="JP",
    )
    profile_id = str(profile["id"])

    gp = await player_profiles.set_player_game_profile(
        workspace_id=ws,
        player_profile_id=profile_id,
        game_id=game_id,
        in_game_name="FighterOne",
    )
    await player_profiles.set_player_character_default(
        workspace_id=ws,
        player_game_profile_id=str(gp["id"]),
        character_id="jin",
        character_name="Jin Kazama",
        is_primary=True,
    )

    # Link entrant to profile
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            """INSERT INTO tournament_player_links (tournament_slug, entrant_id, player_profile_id, workspace_id)
               VALUES (?, ?, ?, ?)""",
            (slug, entrant_id, profile_id, ws),
        )
        await db.commit()

    # Verify initial presentation resolves to Jin
    pres1 = await resolve_entrant_presentation(
        ws,
        EntrantScope(provider="startgg", tournament_slug=slug, event_id=event_id, entrant_id=entrant_id),
    )
    assert pres1.presentation.character.value.name == "Jin Kazama"
    assert pres1.presentation.character.source == "player_profile"

    # 2. Freeze Result Version 1 with Jin
    ver1 = await create_result_version(
        ws,
        {
            "tournament_slug": slug,
            "provider_type": "startgg",
            "provider_account_id": "acc-1",
            "provider_tournament_id": "t-1",
            "event_id": event_id,
            "event_name": "Tekken 8 Singles",
            "game_id": game_id,
            "capture_status": "final",
            "provider_state_raw": "COMPLETED",
            "provider_payload_hash": "hp1",
            "presentation_hash": "hpres1",
            "observation_hash": "hobs1",
            "observed_at": "2026-09-28T10:00:00Z",
            "created_by": user_id,
        },
        [
            {
                "ordinal": 1,
                "placement": 1,
                "entrant_id": entrant_id,
                "entrant_name": "FighterOne",
                "is_tied": False,
                "presentation": {
                    "character": {"value": {"name": "Jin Kazama", "id": "jin"}, "source": "player_profile"},
                    "display_name": {"value": "FighterOne", "source": "player_profile"},
                    "prefix": {"value": "", "source": "player_profile"},
                    "country": {"value": "JP", "source": "player_profile"},
                    "avatar_url": {"value": "", "source": "player_profile"},
                },
                "provider_entry": {},
            }
        ],
    )

    # 3. Apply event-scoped character override: "Kazuya"
    await player_profiles.set_tournament_entrant_override(
        workspace_id=ws,
        provider="startgg",
        tournament_slug=slug,
        event_id=event_id,
        entrant_id=entrant_id,
        data={
            "character_id": "kazuya",
            "character_name": "Kazuya Mishima",
        },
        updated_by=user_id,
    )

    # The event presentation now resolves to Kazuya with source entrant_override
    pres2 = await resolve_entrant_presentation(
        ws,
        EntrantScope(provider="startgg", tournament_slug=slug, event_id=event_id, entrant_id=entrant_id),
    )
    assert pres2.presentation.character.value.name == "Kazuya Mishima"
    assert pres2.presentation.character.source == "entrant_override"

    # BUT the Player Archive profile MUST NOT be silently changed! Still Jin!
    chars_before = await player_profiles.get_player_character_defaults(ws, str(gp["id"]))
    primary_char = next(c for c in chars_before if c["is_primary"])
    assert primary_char["character_id"] == "jin"

    # AND Result Version 1 remains completely immutable (still Jin)
    ver1_read = await get_result_version_by_id(ws, ver1["id"])
    assert ver1_read is not None
    assert ver1_read["id"] == ver1["id"]

    # 4. Explicit profile promotion via API endpoint
    owner_principal = _make_principal(ws, role="owner", user_id=user_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=owner_principal))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-sess")

        # Permission check: Viewer cannot promote override
        viewer_principal = _make_principal(ws, role="viewer", user_id="viewer-1")
        monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=viewer_principal))

        forbid_resp = await client.post(
            "/api/player-profiles/promote-override",
            json={
                "tournament_slug": slug,
                "event_id": event_id,
                "entrant_id": entrant_id,
                "provider": "startgg",
            },
        )
        assert forbid_resp.status_code == 403

        # Owner / Tournament Organizer promotion succeeds
        monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=owner_principal))
        promote_resp = await client.post(
            "/api/player-profiles/promote-override",
            json={
                "tournament_slug": slug,
                "event_id": event_id,
                "entrant_id": entrant_id,
                "provider": "startgg",
            },
        )
        assert promote_resp.status_code == 200, promote_resp.text
        assert promote_resp.json()["ok"] is True

    # 5. Profile is now updated with Kazuya as default character
    chars_after = await player_profiles.get_player_character_defaults(ws, str(gp["id"]))
    new_primary = next((c for c in chars_after if c["is_primary"]), None)
    assert new_primary is not None
    assert new_primary["character_id"] == "kazuya"
    assert new_primary["character_name"] == "Kazuya Mishima"

    # Verify audit trail contains promotion action
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        audit_row = await (await db.execute(
            "SELECT action, target_id FROM audit_events WHERE workspace_id = ? AND action = 'player_profile.promote_override'",
            (ws,),
        )).fetchone()
        assert audit_row is not None
        assert audit_row[0] == "player_profile.promote_override"
        assert audit_row[1] == profile_id
