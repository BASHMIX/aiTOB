"""Start.gg attendance intent is not a bracket-result mutation."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from backend.core import database
from backend.core.contracts import ProviderSetResult, ProviderSetState


class FakeStartGGProvider:
    def __init__(self):
        self.state = ProviderSetState.CALLED
        self.in_progress_calls = 0
        self.dq_winners: list[str] = []

    async def fetch_set_entrant_order(self, _set_id):
        return ["entrant-1", "entrant-2"]

    async def fetch_set_state(self, _set_id):
        return self.state

    async def mark_in_progress(self, set_id):
        self.in_progress_calls += 1
        self.state = ProviderSetState.IN_PROGRESS
        return ProviderSetResult(success=True, set_id=set_id, new_state=self.state)

    async def mark_dq(self, set_id, winner_id):
        self.dq_winners.append(str(winner_id))
        self.state = ProviderSetState.COMPLETE
        return ProviderSetResult(success=True, set_id=set_id, new_state=self.state)


async def _install_provider(monkeypatch):
    provider = FakeStartGGProvider()

    async def resolve(_slug, _workspace_id=None):
        return provider

    monkeypatch.setattr("backend.core.providers.registry.get_provider_for_tournament", resolve)
    return provider


@pytest.fixture
async def startgg_attendance_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "startgg-attendance.pg"))
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

    provider = await _install_provider(monkeypatch)
    response = await matches.api_set_attendance(
        "set-1", AttendanceRequest(player="p2", state="present")
    )

    assert response.ok is True
    match = await database.get_active_match("set-1")
    assert match["p2_attendance_state"] == "present"
    assert match["status"] == "called"
    assert match["hub_status"] == "called"
    assert match["provider_state_normalized"] == "in_progress"
    assert match["attendance_protected_at"]
    assert match["dq_player"] is None
    assert provider.in_progress_calls == 1


@pytest.mark.asyncio
async def test_both_present_starts_and_goes_live_only_after_second_attendee(
    startgg_attendance_db, monkeypatch
):
    from backend.core.match_attendance import AttendanceCommandService

    provider = await _install_provider(monkeypatch)
    await database.upsert_active_match(
        "set-1", is_stream_match=True, station_id="stream-1", broadcast_state="queued"
    )
    service = AttendanceCommandService()

    first = await service.set_attendance(
        "set-1", player="p1", state="present", source="discord"
    )
    assert first["outcome"] == "entrant_protected"
    protected = await database.get_active_match("set-1")
    assert protected["status"] == "called"
    assert protected["broadcast_state"] == "queued"

    second = await service.set_attendance(
        "set-1", player="p2", state="present", source="discord"
    )
    assert second["outcome"] == "both_present_started"
    live = await database.get_active_match("set-1")
    assert live["status"] == "in_progress"
    assert live["hub_status"] == "in_progress"
    assert live["broadcast_state"] == "live"
    assert live["broadcast_started_at"]
    assert provider.in_progress_calls == 1


@pytest.mark.asyncio
async def test_deadline_advances_only_verified_attendee_as_startgg_dq(
    startgg_attendance_db, monkeypatch
):
    from backend.core.match_attendance import AttendanceCommandService

    provider = await _install_provider(monkeypatch)
    service = AttendanceCommandService()
    await service.set_attendance(
        "set-1", player="p2", state="present", source="discord"
    )

    outcome = await service.resolve_deadline("set-1")

    assert outcome["outcome"] == "single_attendee_dq_verified"
    assert outcome["winner_id"] == "entrant-2"
    assert provider.dq_winners == ["entrant-2"]
    match = await database.get_active_match("set-1")
    assert match["status"] == "complete"
    assert match["provider_state_normalized"] == "complete"
    assert match["dq_player"] == "p1"


@pytest.mark.asyncio
async def test_no_attendees_leaves_double_dq_to_startgg(
    startgg_attendance_db, monkeypatch
):
    from backend.core.match_attendance import AttendanceCommandService

    provider = await _install_provider(monkeypatch)
    outcome = await AttendanceCommandService().resolve_deadline("set-1")

    assert outcome["outcome"] == "provider_double_dq"
    assert provider.in_progress_calls == 0
    assert provider.dq_winners == []


@pytest.mark.asyncio
async def test_zero_attendance_is_reconciled_from_provider_without_a_winner(
    startgg_attendance_db, monkeypatch
):
    from backend.core.match_attendance import AttendanceCommandService

    provider = await _install_provider(monkeypatch)
    reads = 0

    async def fetch_state(_set_id):
        nonlocal reads
        reads += 1
        return ProviderSetState.COMPLETE if reads == 2 else ProviderSetState.CALLED

    provider.fetch_set_state = fetch_state
    outcome = await AttendanceCommandService().reconcile_provider_completion(
        "set-1", delays=(0.0, 0.0)
    )

    assert outcome["outcome"] == "provider_double_dq_reconciled"
    assert provider.dq_winners == []
    match = await database.get_active_match("set-1")
    assert match["status"] == "complete"
    assert match["result_kind"] == "double_dq"


@pytest.mark.asyncio
async def test_attendance_decision_cannot_reverse_after_protection(
    startgg_attendance_db, monkeypatch
):
    from backend.core.match_attendance import AttendanceCommandError, AttendanceCommandService

    await _install_provider(monkeypatch)
    service = AttendanceCommandService()
    await service.set_attendance("set-1", player="p1", state="present", source="discord")

    with pytest.raises(AttendanceCommandError, match="cannot be reversed"):
        await service.set_attendance("set-1", player="p1", state="withdrawn", source="discord")


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
