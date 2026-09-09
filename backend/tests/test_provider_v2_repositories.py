"""Dark storage tests: claiming records must never execute an external effect."""
from __future__ import annotations

import pytest

from backend.core import database
from backend.core.storage import dbapi as aiosqlite, is_postgres


@pytest.fixture
async def v2_database(tmp_path, monkeypatch):
    db_path = tmp_path / "provider-v2.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    await database.init_db()
    return database.DB_PATH


@pytest.mark.asyncio
async def test_provider_command_lease_is_idempotent_and_does_not_execute_remote_action(v2_database):
    command = {
        "id": "command-1", "tournament_slug": "tournament-1", "set_id": "match-1",
        "provider_type": "challonge", "provider_account_id": "account-1",
        "action": "report_score", "idempotency_key": "score:match-1:revision-1",
        "payload_digest": "sha256:fixture",
    }
    inserted = await database.create_provider_command_v2(command)
    duplicate = await database.create_provider_command_v2({**command, "id": "command-2"})
    claimed = await database.claim_due_provider_commands_v2(
        "2099-01-01T00:00:00Z", "2099-01-01T00:05:00Z"
    )
    reclaimed = await database.claim_due_provider_commands_v2(
        "2099-01-01T00:06:00Z", "2099-01-01T00:11:00Z"
    )

    assert inserted["id"] == duplicate["id"] == "command-1"
    assert len(claimed) == 1
    assert claimed[0]["state"] == "sending"
    assert claimed[0]["attempt_count"] == 1
    lease_until = claimed[0]["lease_until"]
    if is_postgres():
        assert lease_until.isoformat() == "2099-01-01T00:05:00"
    else:
        assert lease_until == "2099-01-01T00:05:00Z"
    assert reclaimed[0]["attempt_count"] == 2


@pytest.mark.asyncio
async def test_workflow_outbox_lease_recovers_durably_without_dispatching_discord_or_obs(v2_database):
    event = {
        "event_id": "event-1", "match_id": "match-1", "event_type": "discord_call",
        "deduplication_key": "call:match-1:revision-1", "payload": {"message": "fixture"},
    }
    persisted = await database.enqueue_workflow_outbox_v2(event)
    duplicate = await database.enqueue_workflow_outbox_v2({**event, "event_id": "event-2"})
    claimed = await database.claim_due_workflow_outbox_v2(
        "2099-01-01T00:00:00Z", "2099-01-01T00:05:00Z"
    )
    reclaimed = await database.claim_due_workflow_outbox_v2(
        "2099-01-01T00:06:00Z", "2099-01-01T00:11:00Z"
    )

    assert persisted["event_id"] == duplicate["event_id"] == "event-1"
    assert len(claimed) == 1
    assert claimed[0]["status"] == "sending"
    assert claimed[0]["attempts"] == 1
    assert reclaimed[0]["attempts"] == 2

    async with aiosqlite.connect(v2_database) as db:
        async with db.execute("SELECT COUNT(*) FROM workflow_outbox") as cursor:
            assert (await cursor.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_future_hub_workflow_and_outbox_share_one_transaction_without_touching_legacy_status(v2_database):
    async with aiosqlite.connect(v2_database) as db:
        await db.execute(
            "INSERT INTO active_matches (set_id, status) VALUES ('match-atomic', 'not_started')"
        )
        await db.commit()

    await database.update_hub_workflow_and_enqueue_outbox_v2(
        "match-atomic", "called",
        {
            "event_id": "event-atomic", "event_type": "discord_call",
            "deduplication_key": "call:match-atomic:revision-1",
        },
    )
    async with aiosqlite.connect(v2_database) as db:
        async with db.execute(
            "SELECT status, hub_status FROM active_matches WHERE set_id = 'match-atomic'"
        ) as cursor:
            row = await cursor.fetchone()
            status, hub_status = (
                (row["status"], row["hub_status"]) if isinstance(row, dict)
                else tuple(row)
            )
        async with db.execute("SELECT COUNT(*) FROM workflow_outbox") as cursor:
            outbox_count = (await cursor.fetchone())[0]

    assert (status, hub_status, outbox_count) == ("not_started", "called", 1)


@pytest.mark.asyncio
async def test_v2_budget_and_snapshot_cache_are_persistence_only(v2_database):
    await database.upsert_provider_api_budget_v2(
        "challonge", "account-1", estimated_used=18, backoff_until="2099-01-01T00:10:00Z"
    )
    await database.save_provider_snapshot_cache_v2(
        "challonge", "account-1", "tournament-1", "single_match",
        entity_coverage=["match-1"], revision="rev-1", payload={"match": "match-1"},
    )
    await database.record_provider_request_telemetry_v2(
        "challonge", "account-1", "tournament-1", "single_match", 80, "started"
    )
    async with aiosqlite.connect(v2_database) as db:
        async with db.execute("SELECT estimated_used FROM provider_api_budgets") as cursor:
            assert (await cursor.fetchone())[0] == 18
        async with db.execute("SELECT revision FROM provider_snapshot_cache") as cursor:
            assert (await cursor.fetchone())[0] == "rev-1"
        async with db.execute("SELECT disposition FROM provider_request_telemetry") as cursor:
            assert (await cursor.fetchone())[0] == "started"
