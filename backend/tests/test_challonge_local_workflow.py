"""Phase 7A: Challonge workflow is local, durable, and provider-silent."""
from __future__ import annotations

import json

import pytest

from backend.core import database
from backend.core.storage import dbapi as aiosqlite


@pytest.fixture
async def local_workflow_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "local-workflow.sqlite"))
    await database.init_db()
    slug = "challonge:account:fnc:1"
    await database.upsert_tournament(
        slug, "FNC", None, None, None, json.dumps({}), provider_type="challonge",
        provider_tournament_id="1", provider_account_id="account",
    )
    await database.upsert_active_match(
        "challonge:m1", tournament_slug=slug, p1_name="Alpha", p2_name="Bravo",
        p1_entrant_id="p1", p2_entrant_id="p2", status="not_started",
        provider_state_raw="open", provider_state_normalized="not_started",
        hub_status="available", sync_status="synced",
    )
    await database.upsert_active_match(
        "startgg:m1", tournament_slug="startgg:legacy", p1_name="Legacy A", p2_name="Legacy B",
        status="not_started",
    )
    await database.upsert_tournament("startgg:legacy", "Legacy", None, None, None, json.dumps({}))
    await database.upsert_active_match("challonge:other", tournament_slug=slug, p1_name="Other A", p2_name="Other B", status="called", station_id="station-b")
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO stations (id, name) VALUES ('station-a', 'Station A')")
        await db.execute("INSERT INTO stations (id, name) VALUES ('station-b', 'Station B')")
        await db.commit()
    return slug


@pytest.mark.asyncio
async def test_challonge_call_ready_start_and_station_are_atomic_and_provider_silent(local_workflow_db, monkeypatch):
    from backend.core.match_commands import MatchCommandService

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("Challonge local workflow must not resolve or call a provider")

    service = MatchCommandService(feature_flags={"CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true"})
    monkeypatch.setattr(service, "_provider_for_match", forbidden_provider)

    called = await service.call("challonge:m1")
    await service.mark_ready("challonge:m1", "p1")
    await service.mark_ready("challonge:m1", "p2")
    started = await service.start("challonge:m1")
    assigned = await service.assign_station("challonge:m1", "station-a")

    assert called["outcome"] == started["outcome"] == assigned["outcome"] == "local_only"
    match = await database.get_active_match("challonge:m1")
    assert (match["status"], match["hub_status"], match["sync_status"]) == ("in_progress", "in_progress", "local_only")
    assert match["p1_ready"] == match["p2_ready"] == 1
    assert match["station_id"] == "station-a"

    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM provider_reconciliation_audit WHERE set_id='challonge:m1'") as cursor:
            assert (await cursor.fetchone())[0] == 5
        async with db.execute("SELECT event_type, COUNT(*) FROM workflow_outbox WHERE match_id='challonge:m1' GROUP BY event_type") as cursor:
                effect_rows = await cursor.fetchall()
                effects = {
                    (row["event_type"], row["count"]) if isinstance(row, dict) else tuple(row)
                    for row in effect_rows
                }
                effects = dict(effects)
        async with db.execute("SELECT active_match_id FROM stations WHERE id='station-a'") as cursor:
            assert (await cursor.fetchone())[0] == "challonge:m1"
    assert effects == {"discord_call": 1, "discord_ready": 2, "obs_match_started": 1, "obs_station_assigned": 1}


@pytest.mark.asyncio
async def test_challonge_stream_station_assignment_marks_the_local_match_on_stream(local_workflow_db, monkeypatch):
    """The local station workflow must not bypass the stream-panel projection."""
    from backend.core.match_commands import MatchCommandService

    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("UPDATE stations SET is_stream_station=TRUE WHERE id='station-a'")
        await db.commit()

    service = MatchCommandService(feature_flags={"CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true"})
    await service.call("challonge:m1")
    await service.start("challonge:m1")
    await service.assign_station("challonge:m1", "station-a")

    match = await database.get_active_match("challonge:m1")
    assert match["station_id"] == "station-a"
    assert match["is_stream_match"] == 1
    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute("SELECT active_match_id FROM stations WHERE id='station-a'") as cursor:
            assert (await cursor.fetchone())[0] == "challonge:m1"


@pytest.mark.asyncio
async def test_challonge_local_workflow_rejects_unresolved_or_occupied_station_without_writes(local_workflow_db):
    from backend.core.match_commands import MatchCommandService, MatchCommandError

    await database.upsert_active_match("challonge:tbd", tournament_slug=local_workflow_db, p1_name="Alpha", p2_name="TBD", status="not_started")
    service = MatchCommandService(feature_flags={"CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true"})

    with pytest.raises(MatchCommandError, match="two resolved entrants"):
        await service.call("challonge:tbd")
    with pytest.raises(MatchCommandError, match="already occupied"):
        await service.assign_station("challonge:m1", "station-b")

    assert await database.get_active_match("challonge:tbd")
    assert (await database.get_active_match("challonge:tbd"))["status"] == "not_started"


@pytest.mark.asyncio
async def test_legacy_startgg_does_not_enter_the_local_challonge_path(local_workflow_db):
    from backend.core.match_commands import MatchCommandService, MatchCommandError

    service = MatchCommandService(feature_flags={"CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true"})
    with pytest.raises(MatchCommandError, match="not enabled"):
        await service.call("startgg:m1")


@pytest.mark.asyncio
async def test_hub_routes_use_the_local_challonge_service_without_provider_lifecycle(local_workflow_db, monkeypatch):
    from backend.api.routers import matches
    from backend.api.schemas import PatchActiveMatchRequest, PlayerReadyRequest

    monkeypatch.setenv("CHALLONGE_LOCAL_WORKFLOW_ENABLED", "true")

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("Local Challonge endpoint attempted a provider lifecycle call")

    monkeypatch.setattr(matches, "get_provider_for_tournament", forbidden_provider)
    assert (await matches.api_call_match("challonge:m1")).ok is True
    assert (await matches.api_player_ready("challonge:m1", PlayerReadyRequest(player="p1"))).ok is True
    assert (await matches.api_player_ready("challonge:m1", PlayerReadyRequest(player="p2"))).ok is True
    assert (await matches.api_activate_match("challonge:m1")).ok is True

    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("UPDATE stations SET is_stream_station=TRUE WHERE id='station-a'")
        await db.commit()
    assert (await matches.api_patch_active_match(
        "challonge:m1", PatchActiveMatchRequest(station_id="station-a"),
    )).ok is True
    match = await database.get_active_match("challonge:m1")
    assert match["is_stream_match"] == 1


@pytest.mark.asyncio
async def test_challonge_discord_recipients_require_verified_stable_identity_links(local_workflow_db):
    from backend.core.identity_links import save_identity_override
    from backend.core.match_commands import MatchCommandService

    await save_identity_override({
        "provider_type": "challonge", "tournament_slug": local_workflow_db,
        "provider_entrant_id": "p1", "discord_user_id": "discord-alpha",
        "display_name_snapshot": "Alpha",
    })
    await MatchCommandService(feature_flags={"CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true"}).call("challonge:m1")
    match = await database.get_active_match("challonge:m1")
    assert match["p1_discord"] == "discord-alpha"
    assert match["p2_discord"] is None


@pytest.mark.asyncio
async def test_challonge_score_dq_and_reset_are_rejected_before_any_provider_call(local_workflow_db, monkeypatch):
    from fastapi import HTTPException
    from backend.api.routers import matches
    from backend.api.schemas import DQRequest

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("A disabled Challonge remote action called a provider")

    monkeypatch.setattr(matches, "get_provider_for_tournament", forbidden_provider)
    for operation in (
        lambda: matches.api_send_match("challonge:m1"),
        lambda: matches.api_reset_match("challonge:m1"),
        lambda: matches.api_dq_match("challonge:m1", DQRequest(player="p1")),
    ):
        with pytest.raises(HTTPException) as exc:
            await operation()
        assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_challonge_double_dq_explains_that_no_winner_can_be_fabricated(local_workflow_db, monkeypatch):
    from fastapi import HTTPException
    from backend.api.routers import matches
    from backend.api.schemas import DQRequest

    async def forbidden_provider(*_args, **_kwargs):
        raise AssertionError("A disabled Challonge double-DQ called a provider")

    monkeypatch.setattr(matches, "get_provider_for_tournament", forbidden_provider)
    with pytest.raises(HTTPException) as exc:
        await matches.api_dq_match("challonge:m1", DQRequest(player="both"))
    assert exc.value.status_code == 409
    assert "both players" in str(exc.value.detail).lower()
    assert "winner" in str(exc.value.detail).lower()
