"""Regression coverage for the platform-wide no-automatic-DQ boundary.

Attendance expiry, process recovery, Discord ready-checks, and the organizer
assistant may request review or explain the next manual action. None of those
flows may invoke the provider DQ mutation. These tests intentionally use
SQLite fixtures and local fakes so they run in the repository test environment
without Discord, provider, or AI credentials.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.core import database


SLUG = "no-automatic-dq/test"
EXPIRED_MATCH = "no-dq-expired"
NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


@pytest.fixture
async def no_auto_dq_db(tmp_path, monkeypatch):
    """Create a disposable database with a called, expired match."""

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "no-automatic-dq.sqlite"))
    await database.init_db()
    await database.upsert_tournament(
        SLUG,
        "No Automatic DQ",
        "SF6",
        "event-1",
        "SF6",
        json.dumps({}),
        provider_type="startgg",
        provider_tournament_id="tournament-1",
    )
    await database.upsert_active_match(
        EXPIRED_MATCH,
        tournament_slug=SLUG,
        status="called",
        hub_status="called",
        attendance_deadline=(NOW - timedelta(minutes=5)).isoformat(),
        auto_dq_disarmed=0,
    )
    yield


async def _provider_dq_ledger_count(set_id: str) -> int:
    from backend.core.storage import dbapi as aiosqlite

    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM provider_command_ledger WHERE set_id=? AND action='dq'",
            (set_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return int(row[0])


@pytest.mark.asyncio
async def test_attendance_expiry_requests_review_without_dq(no_auto_dq_db, monkeypatch):
    """An expired attendance deadline becomes review work only."""

    from backend.core import match_state
    from backend.core.recovery import RecoveryService

    automatic_dq = AsyncMock(side_effect=AssertionError("attendance expiry must not auto-DQ"))
    monkeypatch.setattr(match_state, "auto_dq_match", automatic_dq)

    report = await RecoveryService().restore()

    assert report.overdue_deadlines == (EXPIRED_MATCH,)
    match = await database.get_active_match(EXPIRED_MATCH)
    assert match["sync_status"] == "needs_review"
    assert match.get("dq_player") is None
    assert await _provider_dq_ledger_count(EXPIRED_MATCH) == 0
    automatic_dq.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_restart_recovery_never_replays_a_dq(no_auto_dq_db, monkeypatch):
    """A fresh worker context must not turn a persisted expiry into a DQ."""

    from backend.core import match_state
    from backend.core.recovery import RecoveryService

    automatic_dq = AsyncMock(side_effect=AssertionError("recovery must not replay an automatic DQ"))
    monkeypatch.setattr(match_state, "auto_dq_match", automatic_dq)

    first_worker = RecoveryService()
    first_report = await first_worker.restore()
    await first_worker.close()

    second_worker = RecoveryService()
    second_report = await second_worker.restore()
    await second_worker.close()

    assert first_report.overdue_deadlines == second_report.overdue_deadlines == (EXPIRED_MATCH,)
    match = await database.get_active_match(EXPIRED_MATCH)
    assert match.get("dq_player") is None
    assert await _provider_dq_ledger_count(EXPIRED_MATCH) == 0
    automatic_dq.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_ready_check_expiry_never_invokes_dq(monkeypatch):
    """A Discord timeout may warn, but cannot issue a provider DQ."""

    from backend.bot import match_threads
    from backend.core import match_state

    match = {
        "set_id": "discord-timeout",
        "status": "called",
        "workspace_id": "workspace-a",
        "tournament_slug": SLUG,
        # Explicitly exercise the old enabled/default path as well as the
        # disarmed path. Platform policy must hold in either representation.
        "auto_dq_disarmed": 0,
    }
    thread = SimpleNamespace(send=AsyncMock())
    automatic_dq = AsyncMock(side_effect=AssertionError("Discord expiry must not auto-DQ"))
    real_sleep = asyncio.sleep

    async def no_wait(_seconds: float) -> None:
        await real_sleep(0)

    async def get_match(_set_id: str, _workspace_id: str | None = None) -> dict:
        return dict(match)

    monkeypatch.setattr(match_threads.asyncio, "sleep", no_wait)
    monkeypatch.setattr(match_threads, "get_active_match", get_match)
    monkeypatch.setattr(match_state, "auto_dq_match", automatic_dq)

    await match_threads.run_ready_check_timeout(
        bot=None,
        thread=thread,
        set_id=match["set_id"],
        timeout_seconds=0,
        workspace_id=match["workspace_id"],
    )

    automatic_dq.assert_not_awaited()


@pytest.mark.asyncio
async def test_assistant_result_flow_is_read_only_and_never_invokes_dq(monkeypatch):
    """AI result interpretation and legacy DQ tools stay non-mutating."""

    from backend.bot import main
    from backend.bot.agent.graph import evaluate_chat
    from backend.core import match_state

    automatic_dq = AsyncMock(side_effect=AssertionError("assistant must not auto-DQ"))
    monkeypatch.setattr(match_state, "auto_dq_match", automatic_dq)
    message = SimpleNamespace(channel=SimpleNamespace(send=AsyncMock()))

    assert await evaluate_chat({"match_status": "completed", "chat_history": []}) == {}
    await main.handle_match_state_update(message, {"match_status": "completed"}, bot_instance=None)
    blocked = await main.dq_player_tool.ainvoke({"set_id": "assistant-match", "player_to_dq": "p1"})

    assert "cannot disqualify" in blocked.lower()
    automatic_dq.assert_not_awaited()
