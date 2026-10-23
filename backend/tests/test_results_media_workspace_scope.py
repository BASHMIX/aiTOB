"""Tests for Results Media Workspace boundary security and enumeration prevention."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core.results_media_repository import (
    create_media_output,
    create_result_version,
)
from backend.core.workspace_auth import SessionPrincipal


def _make_principal(workspace_id: str, role: str = "owner") -> SessionPrincipal:
    return SessionPrincipal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        role=role,
        session_id=f"sess-{workspace_id}",
    )


@pytest.mark.asyncio
async def test_results_media_workspace_isolation(postgres_repository_database, monkeypatch):
    """Verify cross-workspace access is strictly rejected with 404 to avoid enumeration."""
    ws_a = "ws-res-iso-a"
    ws_b = "ws-res-iso-b"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        for ws in [ws_a, ws_b]:
            await db.execute(
                "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (ws, f"slug-{ws}", f"Name {ws}"),
            )
            await db.execute(
                "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING",
                (f"user-{ws}", f"{ws}@test.com", f"user_{ws}"),
            )
            await db.execute(
                "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner') ON CONFLICT DO NOTHING",
                (ws, f"user-{ws}"),
            )
        await db.commit()

    # Workspace A creates a version and an output
    version_data = {
        "tournament_slug": "tourney-a",
        "provider_type": "startgg",
        "provider_account_id": "acc-a",
        "provider_tournament_id": "t-1",
        "event_id": "ev-1",
        "event_name": "Tekken 8",
        "capture_status": "final",
        "provider_state_raw": "COMPLETED",
        "provider_payload_hash": "hash-p-a",
        "presentation_hash": "hash-pres-a",
        "observation_hash": "hash-obs-a",
        "observed_at": "2026-09-28T10:00:00Z",
        "created_by": f"user-{ws_a}",
    }
    entries = [
        {
            "ordinal": 1,
            "placement": 1,
            "entrant_id": "e-1",
            "entrant_name": "Player A",
            "is_tied": False,
            "presentation": {"display_name": {"value": "Player A", "source": "provider_snapshot"}},
            "provider_entry": {},
        }
    ]
    version_a = await create_result_version(
        workspace_id=ws_a,
        version_data=version_data,
        entries=entries,
    )

    output_a = await create_media_output(
        workspace_id=ws_a,
        output_data={
            "result_version_id": version_a["id"],
            "output_kind": "static",
            "overlay_name": "Post",
            "scene_schema_version": 2,
            "scene_config_json": {"elements": []},
            "scene_hash": "shash-1",
            "cutoff": "top8",
            "page_number": 1,
            "output_profile_json": {"width": 1920, "height": 1080},
            "created_by": f"user-{ws_a}",
        },
    )

    # Now act as Workspace B principal
    principal_b = _make_principal(ws_b, role="owner")
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal_b))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-session")

        # 1. Workspace B reading Workspace A's version directly returns 404
        res_v = await client.get(f"/api/results-media/versions/{version_a['id']}")
        assert res_v.status_code == 404

        # 2. Workspace B creating output for Workspace A's version returns 404
        res_out = await client.post(
            f"/api/results-media/versions/{version_a['id']}/outputs",
            json={
                "output_kind": "static",
                "scene": {"elements": []},
                "cutoff": "top8",
                "page_number": 1,
                "output_profile": {"width": 1920, "height": 1080, "transparent": False},
            },
        )
        assert res_out.status_code == 404

        # 3. Workspace B posting export receipt for Workspace A's output returns 404
        res_rec = await client.post(
            f"/api/results-media/outputs/{output_a['id']}/export-receipt",
            json={"byte_size": 500, "sha256": "f" * 64},
        )
        assert res_rec.status_code == 404

        # 4. Workspace B asking for latest results of Workspace A's tournament returns 404
        res_latest = await client.get("/api/tournaments/tourney-a/events/ev-1/results/latest")
        assert res_latest.status_code == 404
