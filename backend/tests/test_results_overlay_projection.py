"""Tests for /obs/{station_id}/data projection kind and results projection payload."""

from __future__ import annotations

import json
import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core.overlay_access import issue_overlay_access
from backend.core.results_media_repository import (
    bind_station_session,
    create_media_output,
    create_result_version,
    update_station_session_command,
)


@pytest.mark.asyncio
async def test_results_overlay_projection(postgres_repository_database):
    """Verify projection_kind selection and tournament-results projection payload."""
    ws = "ws-proj-test"
    user_id = "user-proj-1"
    station_id = "station-proj-1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (ws, "proj-ws", "Projection WS"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING",
            (user_id, "proj@example.com", "projuser"),
        )
        await db.execute(
            "INSERT INTO stations (id, name, workspace_id) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (station_id, "Stage 1", ws),
        )
        await db.commit()

    # Issue an access token for the station
    token_id, token = await issue_overlay_access(
        workspace_id=ws,
        station_public_id=station_id,
        actor_id=user_id,
    )

    ver = await create_result_version(
        ws,
        {
            "tournament_slug": "t-proj",
            "provider_type": "startgg",
            "provider_account_id": "acc-1",
            "provider_tournament_id": "t-1",
            "event_id": "ev-proj-1",
            "event_name": "Street Fighter 6 Singles",
            "game_name": "Street Fighter 6",
            "capture_status": "final",
            "provider_state_raw": "COMPLETED",
            "provider_payload_hash": "hp",
            "presentation_hash": "hpres",
            "observation_hash": "hobs-proj",
            "observed_at": "2026-09-28T10:00:00Z",
            "created_by": user_id,
        },
        [
            {
                "ordinal": 1,
                "placement": 1,
                "entrant_id": "e-1",
                "entrant_name": "Player 1",
                "is_tied": False,
                "presentation": {},
                "provider_entry": {},
            }
        ],
    )

    out = await create_media_output(
        ws,
        {
            "result_version_id": ver["id"],
            "output_kind": "live",
            "overlay_name": "Results Overlay",
            "scene_schema_version": 2,
            "scene_config": {
                "schemaVersion": 2,
                "dataSource": {"kind": "tournament-results"},
                "rootIds": ["results"],
                "nodes": {},
            },
            "scene_hash": "shash-proj",
            "cutoff": "top8",
            "page_number": 1,
            "output_profile": {"width": 1920, "height": 1080},
            "created_by": user_id,
        },
    )

    headers = {"x-overlay-token": token}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: No active match and no session bound -> current-match with None active_match
        resp1 = await client.get(f"/obs/{station_id}/data", headers=headers)
        assert resp1.status_code == 200, resp1.text
        data1 = resp1.json()
        assert data1["projection_kind"] == "current-match"
        assert data1["results_projection"] is None

        # Case 2: Bind session and take live
        await bind_station_session(
            workspace_id=ws,
            station_id=station_id,
            media_output_id=out["id"],
            expected_revision=0,
            user_id=user_id,
        )
        await update_station_session_command(
            workspace_id=ws,
            station_id=station_id,
            new_state="live",
            new_cue_index=0,
            expected_revision=1,
            user_id=user_id,
        )

        resp2 = await client.get(f"/obs/{station_id}/data", headers=headers)
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()
        assert data2["projection_kind"] == "tournament-results"
        assert data2["active_match"] is None
        assert data2["config"]["schemaVersion"] == 2
        rp = data2["results_projection"]
        assert rp is not None
        assert rp["output_id"] == out["id"]
        assert rp["result_version_id"] == ver["id"]
        assert rp["capture_status"] == "final"
        assert rp["event"]["name"] == "Street Fighter 6 Singles"
        assert rp["event"]["game_name"] == "Street Fighter 6"
        assert len(rp["entries"]) == 1
        assert rp["session"]["state"] == "live"
        assert rp["session"]["cue_index"] == 0
        assert rp["session"]["session_revision"] == 2

        # Case 3: When active match exists, it takes precedence (current-match)
        from backend.core.database import upsert_active_match
        await upsert_active_match(
            set_id="set-1",
            station_id=station_id,
            tournament_slug="t-proj",
            status="in_progress",
            p1_name="Player A",
            p2_name="Player B",
            workspace_id=ws,
        )

        resp3 = await client.get(f"/obs/{station_id}/data", headers=headers)
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["projection_kind"] == "current-match"
        assert data3["active_match"] is not None
        assert data3["active_match"]["set_id"] == "set-1"
        assert data3["results_projection"] is None
