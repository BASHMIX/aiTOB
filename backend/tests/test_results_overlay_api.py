"""API tests for station results overlay session and command endpoints."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core.results_media_repository import create_media_output, create_result_version
from backend.core.workspace_auth import SessionPrincipal
from backend.tests.results_media_test_support import valid_results_scene


def _make_principal(workspace_id: str, role: str = "owner", user_id: str = "user-test") -> SessionPrincipal:
    return SessionPrincipal(
        user_id=user_id,
        workspace_id=workspace_id,
        role=role,
        session_id=f"sess-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_results_overlay_session_api_flow(postgres_repository_database, monkeypatch):
    """Test session GET, PUT bind, CAS conflict, permissions, and command execution."""
    ws = "ws-sess-api"
    user_id = f"user-{ws}"
    station_id = "station-api-1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (ws, "sess-ws", "Session WS"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING",
            (user_id, "sessapi@example.com", "sessuser"),
        )
        await db.execute(
            "INSERT INTO stations (id, name, workspace_id) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (station_id, "Main Stream", ws),
        )
        await db.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner') ON CONFLICT DO NOTHING",
            (ws, user_id),
        )
        await db.commit()

    ver = await create_result_version(
        ws,
        {
            "tournament_slug": "t-sess-api",
            "provider_type": "startgg",
            "provider_account_id": "acc-1",
            "provider_tournament_id": "t-1",
            "event_id": "ev-api-1",
            "event_name": "Singles Top 8",
            "capture_status": "final",
            "provider_state_raw": "COMPLETED",
            "provider_payload_hash": "hash-p",
            "presentation_hash": "hash-pres",
            "observation_hash": "hash-obs-api",
            "observed_at": datetime.now(UTC).isoformat(),
            "created_by": user_id,
        },
        [
            {
                "ordinal": 1,
                "placement": 1,
                "entrant_id": "e-1",
                "entrant_name": "Champion Player",
                "is_tied": False,
                "presentation": {},
                "provider_entry": {},
            },
            {
                "ordinal": 2,
                "placement": 2,
                "entrant_id": "e-2",
                "entrant_name": "Runner Up",
                "is_tied": False,
                "presentation": {},
                "provider_entry": {},
            },
        ],
    )

    out = await create_media_output(
        ws,
        {
            "result_version_id": ver["id"],
            "output_kind": "live",
            "overlay_name": "Live Top 8",
            "scene_schema_version": 2,
            "scene_config": valid_results_scene(
                ver["id"], mode="sequence", start_delay_ms=0, interval_ms=1
            ),
            "scene_hash": "shash-api",
            "cutoff": "top8",
            "page_number": 1,
            "output_profile": {"width": 1920, "height": 1080},
            "created_by": user_id,
        },
    )

    owner_principal = _make_principal(ws, role="owner", user_id=user_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=owner_principal))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-session")

        # 1. GET initial session before any bind
        resp = await client.get(f"/api/stations/{station_id}/results-session")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["station_id"] == station_id
        assert data["state"] == "cleared"
        assert data["session_revision"] == 0
        assert data["media_output_id"] is None
        assert data["cue_index"] == -1

        # 2. Permission check: Viewer cannot bind session
        viewer_principal = _make_principal(ws, role="viewer", user_id="viewer-user")
        monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=viewer_principal))
        forbidden_resp = await client.put(
            f"/api/stations/{station_id}/results-session",
            json={"media_output_id": out["id"], "expected_revision": 0},
        )
        assert forbidden_resp.status_code == 403

        # Switch back to stream operator / owner
        stream_op_principal = _make_principal(ws, role="stream_operator", user_id=user_id)
        monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=stream_op_principal))

        # 3. Cross-workspace / non-existent media_output_id returns 404
        nf_resp = await client.put(
            f"/api/stations/{station_id}/results-session",
            json={"media_output_id": "00000000-0000-0000-0000-000000000000", "expected_revision": 0},
        )
        assert nf_resp.status_code == 404

        # 4. Successful bind with expected_revision=0
        with patch("backend.api.ws_manager.manager.broadcast_to_slot", new_callable=AsyncMock) as mock_slot_bc, \
             patch("backend.api.ws_manager.manager.broadcast", new_callable=AsyncMock) as mock_bc:
            bind_resp = await client.put(
                f"/api/stations/{station_id}/results-session",
                json={"media_output_id": out["id"], "expected_revision": 0},
            )
            assert bind_resp.status_code == 200, bind_resp.text
            bound_data = bind_resp.json()
            assert bound_data["state"] == "ready"
            assert bound_data["session_revision"] == 1
            assert bound_data["media_output_id"] == out["id"]
            assert bound_data["cue_index"] == -1

            assert mock_slot_bc.called
            assert mock_bc.called

        # 5. CAS conflict on bind with stale revision
        conflict_bind = await client.put(
            f"/api/stations/{station_id}/results-session",
            json={"media_output_id": out["id"], "expected_revision": 0},
        )
        assert conflict_bind.status_code == 409

        # 6. Invalid command transition: hold while in ready state -> 422
        inv_cmd = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "hold", "expected_revision": 1},
        )
        assert inv_cmd.status_code == 422

        # 7. Take Live command: valid from ready state
        with patch("backend.api.ws_manager.manager.broadcast_to_slot", new_callable=AsyncMock) as mock_slot_bc:
            take_live_resp = await client.post(
                f"/api/stations/{station_id}/results-session/commands",
                json={"command": "take_live", "expected_revision": 1},
            )
            assert take_live_resp.status_code == 200, take_live_resp.text
            live_data = take_live_resp.json()
            assert live_data["state"] == "live"
            assert live_data["session_revision"] == 2
            assert live_data["cue_index"] == -1

        # 8. Next command: increments cue_index to 0
        next_resp = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "next", "expected_revision": 2},
        )
        assert next_resp.status_code == 200
        assert next_resp.json()["cue_index"] == 0
        assert next_resp.json()["session_revision"] == 3

        # 9. Next command again: increments cue_index to 1 (capped at max cue len(entries)-1 = 1)
        next_resp2 = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "next", "expected_revision": 3},
        )
        assert next_resp2.status_code == 200
        assert next_resp2.json()["cue_index"] == 1
        assert next_resp2.json()["session_revision"] == 4

        # 10. Next command when already capped stays at 1
        next_resp3 = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "next", "expected_revision": 4},
        )
        assert next_resp3.status_code == 200
        assert next_resp3.json()["cue_index"] == 1
        assert next_resp3.json()["session_revision"] == 5

        # 11. Stale revision on command returns 409
        stale_cmd = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "previous", "expected_revision": 4},
        )
        assert stale_cmd.status_code == 409

        # 12. Restart then Play All: server advances every persisted cue using
        # the frozen scene timing and completes without a browser-side timer.
        restart_resp = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "restart", "expected_revision": 5},
        )
        assert restart_resp.status_code == 200
        assert restart_resp.json()["cue_index"] == -1
        assert restart_resp.json()["session_revision"] == 6

        play_all_resp = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "play_all", "expected_revision": 6},
        )
        assert play_all_resp.status_code == 200
        assert play_all_resp.json()["state"] == "live"

        completed = None
        for _ in range(30):
            await asyncio.sleep(0.01)
            completed_resp = await client.get(f"/api/stations/{station_id}/results-session")
            completed = completed_resp.json()
            if completed["state"] == "complete":
                break
        assert completed is not None
        assert completed["state"] == "complete"
        assert completed["cue_index"] == 1
        assert completed["session_revision"] == 9

        # 13. Clear command: transitions to cleared, cue_index=-1
        clear_resp = await client.post(
            f"/api/stations/{station_id}/results-session/commands",
            json={"command": "clear", "expected_revision": 9},
        )
        assert clear_resp.status_code == 200
        assert clear_resp.json()["state"] == "cleared"
        assert clear_resp.json()["cue_index"] == -1
        assert clear_resp.json()["session_revision"] == 10
