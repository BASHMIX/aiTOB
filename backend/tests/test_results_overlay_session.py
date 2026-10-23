"""Tests for station results overlay session repository operations and CAS."""

from __future__ import annotations

import asyncio
import pytest

from backend.core import database
from backend.core.results_media_repository import (
    bind_station_session,
    create_media_output,
    create_result_version,
    get_station_session,
    update_station_session_command,
)


@pytest.mark.asyncio
async def test_station_overlay_session_lifecycle(postgres_repository_database):
    """Test bind, CAS revision update, state transitions, and recovery."""
    ws = "ws-sess-test"
    user_id = "user-sess-1"
    station_id = "station-main"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (ws, "slug-sess", "Sess WS"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING",
            (user_id, "sess@test.com", "sessuser"),
        )
        await db.execute(
            "INSERT INTO stations (id, name, workspace_id) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (station_id, "Main Station", ws),
        )
        await db.commit()

    # 1. Initially no session
    initial_sess = await get_station_session(ws, station_id)
    assert initial_sess is None

    # 2. Create version and output
    ver = await create_result_version(
        ws,
        {
            "tournament_slug": "t-sess",
            "provider_type": "startgg",
            "provider_account_id": "acc-1",
            "provider_tournament_id": "t-1",
            "event_id": "ev-1",
            "event_name": "Tekken Top 8",
            "capture_status": "final",
            "provider_state_raw": "COMPLETED",
            "provider_payload_hash": "hash-p",
            "presentation_hash": "hash-pres",
            "observation_hash": "hash-obs-sess",
            "observed_at": "2026-09-28T10:00:00Z",
            "created_by": user_id,
        },
        [
            {
                "ordinal": 1,
                "placement": 1,
                "entrant_id": "e-1",
                "entrant_name": "Knee",
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
            "overlay_name": "Live Top 8",
            "scene_schema_version": 2,
            "scene_config": {"elements": []},
            "scene_hash": "shash-live",
            "cutoff": "top8",
            "page_number": 1,
            "output_profile": {"width": 1920, "height": 1080},
            "created_by": user_id,
        },
    )

    # 3. Bind session with expected_revision = 0
    bound = await bind_station_session(
        workspace_id=ws,
        station_id=station_id,
        media_output_id=out["id"],
        expected_revision=0,
        user_id=user_id,
    )
    assert bound is not None
    assert bound["state"] == "ready"
    assert bound["session_revision"] == 1
    assert bound["media_output_id"] == out["id"]
    assert bound["cue_index"] == -1

    # 4. Advance command (Next): state -> 'live', cue_index -> 0, revision 1 -> 2
    cmd1 = await update_station_session_command(
        workspace_id=ws,
        station_id=station_id,
        new_state="live",
        new_cue_index=0,
        expected_revision=1,
        user_id=user_id,
    )
    assert cmd1 is not None
    assert cmd1["state"] == "live"
    assert cmd1["cue_index"] == 0
    assert cmd1["session_revision"] == 2

    # 5. CAS conflict on stale expected_revision (1 instead of 2)
    stale_cmd = await update_station_session_command(
        workspace_id=ws,
        station_id=station_id,
        new_state="live",
        new_cue_index=1,
        expected_revision=1,
        user_id=user_id,
    )
    assert stale_cmd is None

    # 6. Reconnect read retains active live state and revision
    read_reconnect = await get_station_session(ws, station_id)
    assert read_reconnect is not None
    assert read_reconnect["state"] == "live"
    assert read_reconnect["cue_index"] == 0
    assert read_reconnect["session_revision"] == 2

    # 7. Clear command: state -> 'cleared', cue_index -> -1
    cleared = await update_station_session_command(
        workspace_id=ws,
        station_id=station_id,
        new_state="cleared",
        new_cue_index=-1,
        expected_revision=2,
        user_id=user_id,
    )
    assert cleared is not None
    assert cleared["state"] == "cleared"
    assert cleared["cue_index"] == -1
    assert cleared["session_revision"] == 3

    # 8. Concurrent operators using the same revision cannot both advance.
    concurrent = await asyncio.gather(*[
        update_station_session_command(
            workspace_id=ws,
            station_id=station_id,
            new_state="live",
            new_cue_index=0,
            expected_revision=3,
            user_id=user_id,
        )
        for _ in range(2)
    ])
    assert sum(item is not None for item in concurrent) == 1
    after_race = await get_station_session(ws, station_id)
    assert after_race is not None
    assert after_race["session_revision"] == 4
    assert after_race["cue_index"] == 0
