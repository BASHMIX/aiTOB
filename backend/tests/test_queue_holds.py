"""Explicit cutover holds never re-enter worker queues after restart."""

import json

import pytest

from backend.core import database
from backend.core.workflow_outbox import WorkflowOutboxWorker


@pytest.mark.asyncio
async def test_explicit_hold_is_atomic_audited_and_not_claimable():
    await database.init_db()
    workspace_id = "hold-workspace"
    event_id = "hold-event"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
            (workspace_id, "hold-workspace", "Hold Workspace"),
        )
        await db.commit()
    await database.enqueue_workflow_outbox_v2({
        "event_id": event_id,
        "workspace_id": workspace_id,
        "match_id": "hold-match",
        "event_type": "discord_call",
        "payload": {"match_id": "hold-match"},
        "deduplication_key": "hold-event-key",
    })
    await database.add_hub_command("call_match hold-match", workspace_id=workspace_id)
    pending = await database.get_pending_hub_commands(workspace_id)
    command_id = int(pending[0]["id"])

    result = await database.hold_legacy_operations_v2(
        outbox_event_ids=[event_id],
        hub_command_ids=[command_id],
        reason="cutover reconciliation hold",
    )
    assert result == {"outbox_held": 1, "hub_commands_held": 1}
    assert await database.get_pending_hub_commands(workspace_id) == []
    assert await WorkflowOutboxWorker(lambda _event: pytest.fail("held effect dispatched")).run_once() == 0

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        outbox = await (await db.execute(
            "SELECT status, attempts, lease_owner, effect_started_at FROM workflow_outbox WHERE event_id=?",
            (event_id,),
        )).fetchone()
        command = await (await db.execute(
            "SELECT status, attempts, lease_owner, lease_expires_at FROM hub_commands WHERE id=?",
            (command_id,),
        )).fetchone()
        audit = await (await db.execute(
            "SELECT action, target_type, target_id, detail_json FROM audit_events "
            "WHERE action='queue.hold' ORDER BY created_at DESC LIMIT 2",
        )).fetchall()
    assert (outbox[0], outbox[1], outbox[2], outbox[3]) == ("needs_review", 0, None, None)
    assert (command[0], command[1], command[2], command[3]) == ("needs_review", 0, None, None)
    assert len(audit) == 2
    assert {row[1] for row in audit} == {"workflow_outbox", "hub_command"}
    for row in audit:
        detail = json.loads(row[3])
        assert detail["previous_status"] == "pending"
        assert detail["reason"] == "cutover reconciliation hold"


@pytest.mark.asyncio
async def test_hold_precondition_failure_rolls_back_without_partial_update():
    await database.init_db()
    await database.enqueue_workflow_outbox_v2({
        "event_id": "hold-rollback-event",
        "workspace_id": "hold-workspace-2",
        "match_id": "hold-match-2",
        "event_type": "obs_update",
        "payload": {},
        "deduplication_key": "hold-rollback-key",
    })
    with pytest.raises(ValueError, match="Hub command hold precondition failed"):
        await database.hold_legacy_operations_v2(
            outbox_event_ids=["hold-rollback-event"],
            hub_command_ids=[999999],
            reason="must rollback",
        )
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            "SELECT status FROM workflow_outbox WHERE event_id='hold-rollback-event'",
        )).fetchone()
    assert row[0] == "pending"
