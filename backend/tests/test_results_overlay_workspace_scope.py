"""Tests for station results overlay restart reconstruction and two-workspace WebSocket isolation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
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
async def test_restart_reconstruction_and_two_workspace_isolation(postgres_repository_database, monkeypatch):
    """Verify restart state recovery and two-workspace cross-contamination prevention."""
    ws_a = "ws-scope-a"
    user_a = "user-scope-a"
    station_a = "station-a"

    ws_b = "ws-scope-b"
    user_b = "user-scope-b"
    station_b = "station-b"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        for ws, user, st in [(ws_a, user_a, station_a), (ws_b, user_b, station_b)]:
            await db.execute(
                "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (ws, f"slug-{ws}", f"WS {ws}"),
            )
            await db.execute(
                "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING",
                (user, f"{user}@example.com", user),
            )
            await db.execute(
                "INSERT INTO stations (id, name, workspace_id) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (st, f"Stage {st}", ws),
            )
            await db.execute(
                "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner') ON CONFLICT DO NOTHING",
                (ws, user),
            )
        await db.commit()

    # Create version and output for Workspace A
    ver_a = await create_result_version(
        ws_a,
        {
            "tournament_slug": "t-scope-a",
            "provider_type": "startgg",
            "provider_account_id": "acc-a",
            "provider_tournament_id": "t-a",
            "event_id": "ev-a",
            "event_name": "Melee Top 8",
            "capture_status": "final",
            "provider_state_raw": "COMPLETED",
            "provider_payload_hash": "h-a",
            "presentation_hash": "hp-a",
            "observation_hash": "ho-a",
            "observed_at": datetime.now(UTC).isoformat(),
            "created_by": user_a,
        },
        [
            {
                "ordinal": 1,
                "placement": 1,
                "entrant_id": "e-a1",
                "entrant_name": "Zain",
                "is_tied": False,
                "presentation": {},
                "provider_entry": {},
            }
        ],
    )

    out_a = await create_media_output(
        ws_a,
        {
            "result_version_id": ver_a["id"],
            "output_kind": "live",
            "overlay_name": "Melee Overlay",
            "scene_schema_version": 2,
            "scene_config": valid_results_scene(ver_a["id"], mode="sequence"),
            "scene_hash": "shash-a",
            "cutoff": "top8",
            "page_number": 1,
            "output_profile": {"width": 1920, "height": 1080},
            "created_by": user_a,
        },
    )

    # 1. Workspace B operator cannot bind Workspace A's output to Workspace B station
    principal_b = _make_principal(ws_b, role="owner", user_id=user_b)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal_b))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-b")
        denied_bind = await client.put(
            f"/api/stations/{station_b}/results-session",
            json={"media_output_id": out_a["id"], "expected_revision": 0},
        )
        assert denied_bind.status_code == 404

        # Workspace B cannot command Workspace A's station
        denied_cmd = await client.post(
            f"/api/stations/{station_a}/results-session/commands",
            json={"command": "clear", "expected_revision": 0},
        )
        assert denied_cmd.status_code == 404

    # 2. Workspace A binds session and takes live, emitting WS broadcast only for Workspace A
    principal_a = _make_principal(ws_a, role="owner", user_id=user_a)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal_a))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-a")

        with patch("backend.api.ws_manager.manager.broadcast_to_slot", new_callable=AsyncMock) as mock_slot_bc, \
             patch("backend.api.ws_manager.manager.broadcast", new_callable=AsyncMock) as mock_bc:
            bind_resp = await client.put(
                f"/api/stations/{station_a}/results-session",
                json={"media_output_id": out_a["id"], "expected_revision": 0},
            )
            assert bind_resp.status_code == 200

            # Verify slot broadcast was strictly for station_a and ws_a
            mock_slot_bc.assert_called_once()
            call_slot, call_msg, call_ws = mock_slot_bc.call_args[0]
            assert call_slot == station_a
            assert call_ws == ws_a
            assert call_msg["type"] == "results_session_update"

            # Verify global broadcast was scoped to ws_a
            mock_bc.assert_called_once()
            call_payload = mock_bc.call_args[0][0]
            assert call_payload["_workspace_id"] == ws_a

    # 3. Simulate process restart: query /obs/{station_id}/data directly
    token_id, token = await issue_overlay_access(
        workspace_id=ws_a,
        station_public_id=station_a,
        actor_id=user_a,
    )

    # Move to cue 0 and revision 2
    await update_station_session_command(
        workspace_id=ws_a,
        station_id=station_a,
        new_state="live",
        new_cue_index=0,
        expected_revision=1,
        user_id=user_a,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"x-overlay-token": token}
        resp = await client.get(f"/obs/{station_a}/data", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["projection_kind"] == "tournament-results"
        assert data["results_projection"]["session"]["state"] == "live"
        assert data["results_projection"]["session"]["cue_index"] == 0
        assert data["results_projection"]["session"]["session_revision"] == 2
        assert data["results_projection"]["output_id"] == out_a["id"]
