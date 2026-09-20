"""Start.gg attendance intent is not a bracket-result mutation."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from backend.core import database


@pytest.fixture
async def startgg_attendance_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "startgg-attendance.sqlite"))
    await database.init_db()
    await database.upsert_tournament(
        "startgg:attendance",
        "Attendance",
        None,
        None,
        None,
        json.dumps({}),
        provider_type="startgg",
    )
    await database.upsert_active_match(
        "set-1",
        tournament_slug="startgg:attendance",
        p1_name="Alpha",
        p2_name="Bravo",
        p1_entrant_id="entrant-1",
        p2_entrant_id="entrant-2",
        status="called",
        hub_status="called",
        provider_state_raw="called",
        provider_state_normalized="called",
        sync_status="synced",
    )


@pytest.mark.asyncio
async def test_startgg_manual_dq_records_selected_entrant_as_withdrawn_without_result(
    startgg_attendance_db, monkeypatch
):
    from backend.api.routers import matches
    from backend.api.schemas import DQRequest

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("Attendance withdrawal must not send a winner or DQ result")

    monkeypatch.setattr(matches, "get_provider_for_tournament", forbidden_provider)

    response = await matches.api_dq_match("set-1", DQRequest(player="p1"))

    assert response.ok is True
    match = await database.get_active_match("set-1")
    assert match["p1_attendance_state"] == "withdrawn"
    assert match["p2_attendance_state"] == "pending"
    assert match["p1_attendance_updated_at"]
    assert match["status"] == "called"
    assert match["hub_status"] == "called"
    assert match["dq_player"] is None
    assert match["sync_status"] == "needs_review"


@pytest.mark.asyncio
async def test_canonical_attendance_endpoint_records_present_without_advancing(
    startgg_attendance_db, monkeypatch
):
    from backend.api.routers import matches
    from backend.api.schemas import AttendanceRequest

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("No undocumented Start.gg attendance mutation may be called")

    monkeypatch.setattr(matches, "get_provider_for_tournament", forbidden_provider)
    response = await matches.api_set_attendance(
        "set-1", AttendanceRequest(player="p2", state="present")
    )

    assert response.ok is True
    match = await database.get_active_match("set-1")
    assert match["p2_attendance_state"] == "present"
    assert match["status"] == "called"
    assert match["dq_player"] is None


@pytest.mark.asyncio
async def test_startgg_manual_double_dq_is_rejected_without_winner_fallback(
    startgg_attendance_db, monkeypatch
):
    from backend.api.routers import matches
    from backend.api.schemas import DQRequest

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("Double-DQ must be resolved by Start.gg at its deadline")

    monkeypatch.setattr(matches, "get_provider_for_tournament", forbidden_provider)
    with pytest.raises(HTTPException) as exc:
        await matches.api_dq_match("set-1", DQRequest(player="both"))

    assert exc.value.status_code == 409
    assert "start.gg" in str(exc.value.detail).lower()
    match = await database.get_active_match("set-1")
    assert match["p1_attendance_state"] == "pending"
    assert match["p2_attendance_state"] == "pending"
    assert match["status"] == "called"


@pytest.mark.asyncio
async def test_attendance_is_only_available_during_startgg_called_window(
    startgg_attendance_db,
):
    from backend.api.routers import matches
    from backend.api.schemas import AttendanceRequest

    await database.update_active_match("set-1", status="in_progress", hub_status="in_progress")
    with pytest.raises(HTTPException) as exc:
        await matches.api_set_attendance(
            "set-1", AttendanceRequest(player="p1", state="withdrawn")
        )

    assert exc.value.status_code == 409
    assert "called" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_deprecated_automatic_dq_shim_only_requests_review(
    startgg_attendance_db, monkeypatch
):
    from backend.core import match_state

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("Automatic DQ must never resolve a provider")

    monkeypatch.setattr(match_state, "get_provider_for_tournament", forbidden_provider)
    outcome = await match_state.auto_dq_match("set-1")

    assert outcome == {
        "ok": False,
        "skipped": "automatic_dq_disabled",
        "needs_review": True,
    }
    match = await database.get_active_match("set-1")
    assert match["status"] == "called"
    assert match["dq_player"] is None
    assert match["sync_status"] == "needs_review"
