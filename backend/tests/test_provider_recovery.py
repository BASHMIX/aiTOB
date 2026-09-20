"""Phase 8: recovery must work from PostgreSQL with fresh service contexts."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

from backend.core.storage import dbapi
import pytest

from backend.core import database


@pytest.fixture
async def recovery_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "recovery.pg"))
    await database.init_db()
    slug = "challonge:account:recovery:1"
    await database.upsert_tournament(slug, "Recovery", None, None, None, json.dumps({}), provider_type="challonge", provider_tournament_id="1", provider_account_id="account")
    future = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    await database.upsert_active_match("challonge:future", tournament_slug=slug, status="called", hub_status="called", called_at=datetime.now(UTC).isoformat(), player1_ready_at=datetime.now(UTC).isoformat(), attendance_deadline=future, station_id="station-a", discord_thread_id="thread-a")
    await database.upsert_active_match("challonge:overdue", tournament_slug=slug, status="called", hub_status="called", attendance_deadline=past)
    await database.upsert_active_match("challonge:complete", tournament_slug=slug, status="complete", hub_status="complete", attendance_deadline=future)
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO stations (id, name, active_match_id) VALUES ('station-a', 'A', 'challonge:future')")
        await db.commit()
    return slug


@pytest.mark.asyncio
async def test_recovery_uses_fresh_context_and_keeps_call_ready_station_thread(recovery_db):
    from backend.core.recovery import RecoveryService

    first = RecoveryService()
    report = await first.restore()
    await first.close()  # equivalent to closing the prior process context
    second = RecoveryService()
    resumed = await second.restore()

    assert report.future_deadlines == resumed.future_deadlines == ("challonge:future",)
    assert report.overdue_deadlines == resumed.overdue_deadlines == ("challonge:overdue",)
    row = await database.get_active_match("challonge:future")
    assert row["station_id"] == "station-a" and row["discord_thread_id"] == "thread-a"
    assert row["player1_ready_at"] and row["called_at"]
    assert (await database.get_active_match("challonge:overdue"))["sync_status"] == "needs_review"
    await second.close()


@pytest.mark.asyncio
async def test_overdue_timer_requests_review_never_auto_dq(recovery_db):
    from backend.core.recovery import RecoveryService

    report = await RecoveryService().restore()
    assert report.overdue_deadlines == ("challonge:overdue",)
    match = await database.get_active_match("challonge:overdue")
    assert match.get("dq_player") is None
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT COUNT(*) FROM provider_command_ledger WHERE set_id='challonge:overdue'") as cursor:
            assert (await cursor.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_recovery_status_update_requires_match_workspace(recovery_db):
    """A worker carrying the wrong durable tenant cannot update a match."""
    with pytest.raises(ValueError, match="Unknown match"):
        await database.set_match_sync_status_v2(
            "challonge:future", "needs_review", workspace_id="other-workspace",
            reason="must not cross tenant",
        )
    row = await database.get_active_match("challonge:future")
    assert row["sync_status"] != "needs_review"


@pytest.mark.asyncio
async def test_call_timer_only_warns_and_never_auto_dq(monkeypatch):
    from backend.core import match_state

    feeds: list[tuple[str, str]] = []
    real_sleep = asyncio.sleep
    monkeypatch.setattr(match_state.asyncio, "sleep", lambda _seconds: real_sleep(0))
    monkeypatch.setattr(match_state, "get_active_match", lambda _set_id: real_sleep(0, result={"status": "called"}))
    monkeypatch.setattr(match_state, "add_bot_feed", lambda message, level="info": real_sleep(0, result=feeds.append((message, level))))
    async def must_not_run(_set_id):
        raise AssertionError("automatic DQ must remain disabled")
    monkeypatch.setattr(match_state, "auto_dq_match", must_not_run)

    await match_state.start_call_timer("manual-only", timeout_seconds=0)
    assert feeds and "automatic DQ is disabled" in feeds[0][0]


@pytest.mark.asyncio
async def test_competing_outbox_workers_claim_once_and_effect_deduplicates_after_crash(recovery_db):
    from backend.core.workflow_outbox import WorkflowOutboxWorker

    await database.enqueue_workflow_outbox_v2({"event_id": "e1", "match_id": "challonge:future", "event_type": "discord_call", "deduplication_key": "recovery:call", "payload": {}})
    delivered: set[str] = set()
    calls = 0
    async def dispatch(event):
        nonlocal calls
        calls += 1
        delivered.add(event["deduplication_key"])

    one = WorkflowOutboxWorker(dispatch, lease_owner="worker-one")
    two = WorkflowOutboxWorker(dispatch, lease_owner="worker-two")
    results = await asyncio.gather(
        one.run_once(now="2099-01-01T00:00:00+00:00"),
        two.run_once(now="2099-01-01T00:00:00+00:00"),
    )
    assert sum(results) == 1 and calls == 1 and delivered == {"recovery:call"}

    # A Python set is not evidence of Discord-side idempotency. If the receiver
    # may have acted before failure, stop for reconciliation instead of resending.
    await database.enqueue_workflow_outbox_v2({"event_id": "e2", "match_id": "challonge:future", "event_type": "discord_call", "deduplication_key": "recovery:crash", "payload": {}})
    external: set[str] = set()
    attempts = 0
    async def crash_after_effect(event):
        nonlocal attempts
        attempts += 1
        external.add(event["deduplication_key"])
        if attempts == 1:
            raise RuntimeError("crash after Discord accepted effect")
    worker = WorkflowOutboxWorker(crash_after_effect, lease_owner="restarted")
    await worker.run_once(now="2099-01-01T00:02:00+00:00")
    await worker.run_once(now="2099-01-01T00:03:00+00:00")
    assert attempts == 1 and external == {"recovery:crash"}
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute("SELECT status FROM workflow_outbox WHERE event_id='e2'")).fetchone()
        assert row[0] == "needs_review"


@pytest.mark.asyncio
async def test_command_lease_reclaims_in_new_context_without_resending_mutation(recovery_db):
    from backend.core.match_commands import ProviderCommandLifecycle
    from backend.core.provider_commands import ProviderCommandRecoveryWorker

    command = await ProviderCommandLifecycle().create_remote_command(
        match_id="challonge:future", action="score", payload={"score": 2}, expected_result={}, precondition_revision=None,
    )
    # A dead process left an expired sending lease.
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("UPDATE provider_command_ledger SET state='sending', lease_owner='dead', lease_until='2000-01-01T00:00:00+00:00' WHERE id=?", (command["id"],))
        await db.commit()
    verified: list[str] = []
    async def verify(row):
        verified.append(row["id"])
        await database.update_provider_command_state_v2(row["id"], "acknowledged", reason="recovered for verification")
    fresh_context = ProviderCommandRecoveryWorker(verify, lease_owner="fresh")
    assert await fresh_context.run_once(now="2099-01-01T00:00:00+00:00") == 1
    assert verified == [command["id"]]
    assert (await database.get_provider_command_v2(command["id"]))["state"] == "acknowledged"


@pytest.mark.asyncio
async def test_live_scheduler_uses_adaptive_reasons_and_stops_when_completed():
    from backend.core.sync_coordinator import LiveSyncScheduler

    assert LiveSyncScheduler.policy({"mode": "live", "pending_verification": True}) == ("pending_verification", 300)
    assert LiveSyncScheduler.policy({"mode": "live", "active_match": True}) == ("live_active_match", 300)
    assert LiveSyncScheduler.policy({"mode": "live", "called_match": True}) == ("live_called_match", 300)
    assert LiveSyncScheduler.policy({"mode": "live"}) == ("live_idle", 900)
    assert LiveSyncScheduler.policy({"mode": "economy"}) == (None, 0)
    assert LiveSyncScheduler.policy({"mode": "live", "completed": True}) == (None, 0)

    calls = []
    async def sync(slug, reason):
        calls.append((slug, reason))
    async def state(_slug):
        return {"mode": "live", "completed": True}
    scheduler = LiveSyncScheduler(sync, state)
    assert scheduler.start("done") is True
    assert scheduler.start("done") is False
    await asyncio.sleep(0)
    assert calls == []


@pytest.mark.asyncio
async def test_live_scheduler_makes_one_read_then_stops_after_remote_completion():
    from backend.core.sync_coordinator import LiveSyncScheduler

    calls: list[tuple[str, str]] = []
    completed = False
    async def sync(slug, reason):
        nonlocal completed
        calls.append((slug, reason))
        completed = True
    async def state(_slug):
        return {"mode": "live", "active_match": not completed, "completed": completed}
    async def no_wait(_seconds):
        return None
    scheduler = LiveSyncScheduler(sync, state, sleep=no_wait)
    scheduler.start("live-tournament")
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert calls == [("live-tournament", "live_active_match")]


@pytest.mark.asyncio
async def test_result_verification_backoff_is_fast_and_read_only():
    from backend.core.provider_commands import ResultVerificationBackoff

    sleeps: list[int] = []
    reads = 0
    async def sleep(seconds):
        sleeps.append(seconds)
    async def read_only_verification():
        nonlocal reads
        reads += 1
        return reads == 2
    assert await ResultVerificationBackoff(read_only_verification, sleep=sleep).run() is True
    # Checkpoints are measured from acknowledgement, not cumulatively:
    # verification happens at t=5 then t=15 seconds.
    assert sleeps == [5, 10]
    assert reads == 2
