"""API tests for Results Media endpoints, permission enforcement, and receipts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.core import database
from backend.core.contracts import (
    ProviderEventResults,
    ProviderPageMetadata,
    ProviderStandingEntry,
)
from backend.core.results_media_repository import create_result_version
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
async def test_results_media_api_lifecycle(postgres_repository_database, monkeypatch):
    """Test latest, refresh, version, output, and export-receipt flows."""
    workspace_id = "ws-res-api-1"
    user_id = f"user-{workspace_id}"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "res-ws", "Results Workspace"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING",
            (user_id, "res@example.com", "resuser"),
        )
        await db.execute(
            "INSERT INTO tournaments (workspace_id, slug, name, provider_type) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "t-slug", "Tournament Slug", "startgg"),
        )
        await db.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner') ON CONFLICT DO NOTHING",
            (workspace_id, user_id),
        )
        await db.commit()

    principal = _make_principal(workspace_id, role="owner", user_id=user_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("aitob_session", "valid-session")

        # 1. Latest initially 404
        res_latest = await client.get("/api/tournaments/t-slug/events/ev-1/results/latest")
        assert res_latest.status_code == 404

        # 2. Refresh permission check: viewer role denied (403)
        viewer_principal = _make_principal(workspace_id, role="viewer")
        monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=viewer_principal))
        res_forbidden = await client.post("/api/tournaments/t-slug/events/ev-1/results/refresh", json={})
        assert res_forbidden.status_code == 403

        # Restore owner principal
        monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

        # 3. Successful refresh
        mock_provider = AsyncMock()
        mock_provider.provider_type = "startgg"
        mock_snapshot = MagicMock()
        mock_snapshot.observed_at = datetime.now(UTC).isoformat()
        mock_snapshot.revision = None
        mock_snapshot.payload = {
            "event_results": ProviderEventResults(
                event_id="ev-1",
                event_name="Tekken 8 Top 8",
                game_name="Tekken 8",
                is_completed=True,
                completion_state_raw="COMPLETED",
                standings=[
                    ProviderStandingEntry(ordinal=1, placement=1, entrant_id="e-1", entrant_name="Knee"),
                    ProviderStandingEntry(ordinal=2, placement=2, entrant_id="e-2", entrant_name="Arslan"),
                ],
                page=ProviderPageMetadata(number=1, size=2, total_entries=2, has_more=False, is_complete=True),
            )
        }
        mock_provider.fetch_snapshot.return_value = mock_snapshot

        with patch("backend.core.results_media.get_provider_for_tournament", return_value=mock_provider):
            res_refresh = await client.post("/api/tournaments/t-slug/events/ev-1/results/refresh", json={"force": True})
            assert res_refresh.status_code == 200, res_refresh.text
            refresh_data = res_refresh.json()
            assert refresh_data["reused"] is False
            version_id = refresh_data["version"]["id"]
            assert refresh_data["version"]["event_name"] == "Tekken 8 Top 8"

        # 4. Latest now returns the created version
        res_latest_now = await client.get("/api/tournaments/t-slug/events/ev-1/results/latest")
        assert res_latest_now.status_code == 200
        assert res_latest_now.json()["id"] == version_id

        # 5. Read version by ID
        res_version = await client.get(f"/api/results-media/versions/{version_id}?cutoff=top8")
        assert res_version.status_code == 200
        version_data = res_version.json()
        assert len(version_data["entries"]) == 2
        assert version_data["entries"][0]["entrant_name"] == "Knee"

        # 6. Create media output
        output_payload = {
            "output_kind": "static",
            "overlay_name": "Champion Focus Post",
            "scene": valid_results_scene(version_id),
            "cutoff": "top8",
            "page_number": 1,
            "output_profile": {"width": 1920, "height": 1080, "transparent": False},
        }
        res_out = await client.post(f"/api/results-media/versions/{version_id}/outputs", json=output_payload)
        assert res_out.status_code == 201, res_out.text
        output_data = res_out.json()
        output_id = output_data["id"]
        assert output_data["output_kind"] == "static"

        # 7. Record export receipt
        receipt_payload = {
            "byte_size": 1048576,
            "sha256": "a" * 64,
        }
        res_receipt = await client.post(f"/api/results-media/outputs/{output_id}/export-receipt", json=receipt_payload)
        assert res_receipt.status_code == 200
        assert res_receipt.json() == {"output_id": output_id, "recorded": True}

        # 8. The receipt is immutable: identical retries are idempotent while
        # conflicting browser output cannot rewrite the audit record.
        res_receipt_retry = await client.post(
            f"/api/results-media/outputs/{output_id}/export-receipt", json=receipt_payload
        )
        assert res_receipt_retry.status_code == 200
        res_receipt_conflict = await client.post(
            f"/api/results-media/outputs/{output_id}/export-receipt",
            json={"byte_size": 2048, "sha256": "b" * 64},
        )
        assert res_receipt_conflict.status_code == 409

        # 9. A frozen scene must bind the requested version and live output
        # must contain a Sequence-mode Results Group.
        wrong_scene = valid_results_scene("another-version")
        wrong_binding = await client.post(
            f"/api/results-media/versions/{version_id}/outputs",
            json={**output_payload, "scene": wrong_scene},
        )
        assert wrong_binding.status_code == 422
        assert "scene_result_version_binding_mismatch" in str(wrong_binding.json())

        board_live = await client.post(
            f"/api/results-media/versions/{version_id}/outputs",
            json={**output_payload, "output_kind": "live"},
        )
        assert board_live.status_code == 422
        assert "scene_sequence_group_required" in str(board_live.json())

        # 10. Provider-Provisional versions are viewable but never publishable.
        provisional = await create_result_version(
            workspace_id,
            {
                "tournament_slug": "t-slug",
                "provider_type": "startgg",
                "provider_account_id": "account-provisional",
                "provider_tournament_id": "t-slug",
                "event_id": "ev-provisional",
                "event_name": "Active Event",
                "capture_status": "provisional",
                "provider_state_raw": "ACTIVE",
                "provider_payload_hash": "provisional-payload",
                "presentation_hash": "provisional-presentation",
                "observation_hash": "provisional-observation",
                "observed_at": datetime.now(UTC).isoformat(),
                "created_by": user_id,
            },
            [{
                "ordinal": 1,
                "placement": 1,
                "entrant_id": "provisional-entrant",
                "entrant_name": "Still Playing",
                "is_tied": False,
                "presentation": {},
                "provider_entry": {},
            }],
        )
        provisional_payload = {
            **output_payload,
            "scene": valid_results_scene(provisional["id"]),
        }
        provisional_output = await client.post(
            f"/api/results-media/versions/{provisional['id']}/outputs",
            json=provisional_payload,
        )
        assert provisional_output.status_code == 409

        # 11. All-results page 2 uses the frozen scene page size and does not
        # incorrectly jump by the API's former hard-coded 512-row offset.
        paged = await create_result_version(
            workspace_id,
            {
                "tournament_slug": "t-slug",
                "provider_type": "startgg",
                "provider_account_id": "account-paged",
                "provider_tournament_id": "t-slug",
                "event_id": "ev-paged",
                "event_name": "Paged Final",
                "capture_status": "final",
                "provider_state_raw": "COMPLETED",
                "provider_payload_hash": "paged-payload",
                "presentation_hash": "paged-presentation",
                "observation_hash": "paged-observation",
                "observed_at": datetime.now(UTC).isoformat(),
                "created_by": user_id,
            },
            [{
                "ordinal": index,
                "placement": index,
                "entrant_id": f"paged-{index}",
                "entrant_name": f"Paged Entrant {index}",
                "is_tied": False,
                "presentation": {},
                "provider_entry": {},
            } for index in range(1, 19)],
        )
        paged_scene = valid_results_scene(paged["id"])
        results_group = paged_scene["nodes"]["results-group"]
        results_group["cutoff"] = "all"
        results_group["pageSize"] = 16
        paged_output = await client.post(
            f"/api/results-media/versions/{paged['id']}/outputs",
            json={
                **output_payload,
                "scene": paged_scene,
                "cutoff": "all",
                "page_number": 2,
            },
        )
        assert paged_output.status_code == 201, paged_output.text


@pytest.mark.asyncio
async def test_results_refresh_redacts_unknown_provider_failures(
    postgres_repository_database, monkeypatch
):
    workspace_id = "ws-results-redaction"
    user_id = "user-results-redaction"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
            (workspace_id, "redaction-ws", "Redaction Workspace"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash')",
            (user_id, "redaction@example.com", "redaction"),
        )
        await db.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner')",
            (workspace_id, user_id),
        )
        await db.execute(
            "INSERT INTO tournaments (workspace_id, slug, name, provider_type) VALUES (?, ?, ?, ?)",
            (workspace_id, "redaction-event", "Redaction Event", "startgg"),
        )
        await db.commit()

    principal = _make_principal(workspace_id, role="owner", user_id=user_id)
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))
    secret = "super-secret-provider-credential"
    with patch(
        "backend.core.results_media.refresh_event_results",
        new=AsyncMock(side_effect=RuntimeError(f"upstream body leaked {secret}")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("aitob_session", "valid-session")
            response = await client.post(
                "/api/tournaments/redaction-event/events/ev-1/results/refresh",
                json={"force": True},
            )

    assert response.status_code == 422
    assert response.json()["message"] == "Provider results refresh failed"
    assert secret not in response.text
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            "SELECT detail_json FROM audit_events "
            "WHERE workspace_id=? AND action='results.refresh' ORDER BY created_at DESC LIMIT 1",
            (workspace_id,),
        )).fetchone()
    assert row is not None
    assert secret not in str(row[0])
