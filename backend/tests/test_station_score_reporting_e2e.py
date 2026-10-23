from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core import database
from backend.core.contracts import ITournamentProvider, ProviderSetResult
from backend.core.overlay_access import issue_overlay_access

client = TestClient(app)


@pytest.mark.skip(reason="Station Agent plugin compatibility is currently commented out")
@pytest.mark.asyncio
async def test_station_score_reporting_e2e(monkeypatch):
    """End-to-End test of the Station Score Reporting lifecycle:
    1. Intermediate game score (1-0 in FT2): updates score, keeps match in_progress.
    2. Set-winning score (2-1 in FT2) with auto_confirm:
       - Reports score & winner to provider (Start.gg).
       - Completes and closes the match.
       - Advances the station queue, assigning and starting the next match!
    """
    workspace_id = "ws-e2e-station"
    user_id = "user-e2e-station"
    slug = "tournament/e2e-tourney"
    station_public_id = "station_e2e_1"

    # Setup database entities
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "e2e-ws", "E2E Workspace"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (user_id, "station_e2e@example.com", "E2E Tester", "hash"),
        )
        await db.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, user_id, "owner"),
        )
        await db.execute(
            "INSERT INTO stations (id, public_id, name, workspace_id) VALUES (?, ?, ?, ?)",
            (station_public_id, station_public_id, "Station 1", workspace_id),
        )
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name)
               VALUES ('acc-e2e', ?, ?, 'startgg', 'remote', 'Start.gg')""",
            (user_id, workspace_id),
        )
        await db.commit()

    await database.upsert_tournament(
        slug, "E2E Tourney", "", "", "", "{}", provider_type="startgg",
        provider_account_id="acc-e2e", workspace_id=workspace_id,
    )

    # Match 1: Set 101, Best of 3 (FT2), in_progress on station_1
    await database.upsert_active_match(
        "set_101",
        tournament_slug=slug,
        station_id=station_public_id,
        status="in_progress",
        best_of=3,
        p1_name="Ahmad21",
        p2_name="FNCeSports",
        p1_entrant_id="ent_ahmad",
        p2_entrant_id="ent_fnc",
        workspace_id=workspace_id,
    )

    # Match 2: Set 102, Queued in station_queue for station_1
    await database.upsert_active_match(
        "set_102",
        tournament_slug=slug,
        status="called",
        best_of=3,
        p1_name="NextP1",
        p2_name="NextP2",
        p1_entrant_id="ent_next1",
        p2_entrant_id="ent_next2",
        workspace_id=workspace_id,
    )
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO station_queue (station_id, set_id, sort_order) VALUES (?, ?, ?)",
            (station_public_id, "set_102", 0),
        )
        await db.commit()

    # Issue overlay access token
    _tid, token = await issue_overlay_access(workspace_id, station_public_id, user_id)

    # Mock provider
    mock_provider = AsyncMock(spec=ITournamentProvider)
    mock_provider.provider_type = "startgg"
    mock_provider.report_score.return_value = ProviderSetResult(
        success=True, set_id="set_101", error_message=None
    )
    monkeypatch.setattr(
        "backend.core.providers.registry.get_provider_for_tournament",
        AsyncMock(return_value=mock_provider),
    )
    monkeypatch.setattr(
        "backend.core.score_reporting._schedule_post_result_verification", AsyncMock()
    )

    headers = {"X-Overlay-Token": token}

    # ─────────────────────────────────────────────────────────────────
    # Step 1: Intermediate score (1 - 0) with auto_confirm=True
    # Match requires FT2 (2 wins), so 1 - 0 is not complete yet.
    # ─────────────────────────────────────────────────────────────────
    resp1 = client.post(
        f"/obs/{station_public_id}/submit-result",
        json={"set_id": "set_101", "p1_score": 1, "p2_score": 0, "auto_confirm": True},
        headers=headers,
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["ok"] is True
    assert data1["completed"] is False

    # Verify Match 1 is still in_progress and scores are saved
    m1 = await database.get_active_match("set_101", workspace_id)
    assert m1["p1_score"] == 1
    assert m1["p2_score"] == 0
    assert m1["status"] == "in_progress"
    assert m1["station_id"] == station_public_id
    mock_provider.report_score.assert_not_called()

    # ─────────────────────────────────────────────────────────────────
    # Step 2: Final winning score (2 - 1) with auto_confirm=True
    # Match reaches 2 wins -> Should auto-report and transition to complete!
    # ─────────────────────────────────────────────────────────────────
    resp2 = client.post(
        f"/obs/{station_public_id}/submit-result",
        json={"set_id": "set_101", "p1_score": 2, "p2_score": 1, "winner": "p1", "auto_confirm": True},
        headers=headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["ok"] is True
    assert data2["completed"] is True
    assert "reported to Start.gg" in data2["message"]

    # Verify provider was called with the winning scores and winner entrant ID
    mock_provider.report_score.assert_called_once_with(
        set_id="set_101",
        winner_id="ent_ahmad",
        entrant1_id="ent_ahmad",
        entrant2_id="ent_fnc",
        entrant1_score=2,
        entrant2_score=1,
    )

    # Verify Match 1 is now COMPLETE and its station is freed
    m1_final = await database.get_active_match("set_101", workspace_id)
    assert m1_final["status"] == "complete"
    assert m1_final["p1_score"] == 2
    assert m1_final["p2_score"] == 1
    assert m1_final["station_id"] is None

    # ─────────────────────────────────────────────────────────────────
    # Step 3: Verify Station Queue Advanced Automatically!
    # set_102 was in queue -> should now be assigned to station_1 and in_progress!
    # ─────────────────────────────────────────────────────────────────
    m2_now = await database.get_active_match("set_102", workspace_id)
    assert m2_now["station_id"] == station_public_id
    assert m2_now["status"] == "in_progress"


@pytest.mark.skip(reason="Station Agent plugin compatibility is currently commented out")
@pytest.mark.asyncio
async def test_station_score_reporting_manual_confirm_keeps_match_open(monkeypatch):
    """When auto_confirm is False, reaching the winning score should only save the score,
    leaving the match in_progress without auto-reporting to the provider.
    """
    workspace_id = "ws-manual-confirm"
    user_id = "user-manual-confirm"
    slug = "tournament/manual-tourney"
    station_public_id = "station_manual_1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "manual-ws", "Manual WS"),
        )
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (user_id, "manual@example.com", "Manual Tester", "hash"),
        )
        await db.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, user_id, "owner"),
        )
        await db.execute(
            "INSERT INTO stations (id, public_id, name, workspace_id) VALUES (?, ?, ?, ?)",
            (station_public_id, station_public_id, "Manual Station", workspace_id),
        )
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name)
               VALUES ('acc-manual', ?, ?, 'startgg', 'remote', 'Start.gg')""",
            (user_id, workspace_id),
        )
        await db.commit()

    await database.upsert_tournament(
        slug, "Manual Tourney", "", "", "", "{}", provider_type="startgg",
        provider_account_id="acc-manual", workspace_id=workspace_id,
    )

    await database.upsert_active_match(
        "set_manual_1",
        tournament_slug=slug,
        station_id=station_public_id,
        status="in_progress",
        best_of=3,
        p1_name="PlayerA",
        p2_name="PlayerB",
        p1_entrant_id="ent_a",
        p2_entrant_id="ent_b",
        workspace_id=workspace_id,
    )

    _tid, token = await issue_overlay_access(workspace_id, station_public_id, user_id)
    mock_provider = AsyncMock(spec=ITournamentProvider)
    mock_provider.provider_type = "startgg"
    monkeypatch.setattr(
        "backend.core.providers.registry.get_provider_for_tournament",
        AsyncMock(return_value=mock_provider),
    )

    # Submit final score 2 - 0 but with auto_confirm = False
    resp = client.post(
        f"/obs/{station_public_id}/submit-result",
        json={"set_id": "set_manual_1", "p1_score": 2, "p2_score": 0, "auto_confirm": False},
        headers={"X-Overlay-Token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["completed"] is False

    # Verify provider was NOT called
    mock_provider.report_score.assert_not_called()

    # Verify match is still in_progress with recorded score
    m = await database.get_active_match("set_manual_1", workspace_id)
    assert m["status"] == "in_progress"
    assert m["p1_score"] == 2
    assert m["p2_score"] == 0
    assert m["station_id"] == station_public_id

