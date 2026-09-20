"""Action proposals stay inert until an authenticated organizer approves them."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from backend.core.storage import dbapi
import pytest

from backend.core import database
from backend.core.action_proposals import (
    ProposalError, approve_action_proposal, create_action_proposal,
    execute_approved_proposal, reject_action_proposal,
)

FIRST, OTHER = "proposal/first", "proposal/other"


@pytest.fixture
async def proposal_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "proposals.pg"))
    await database.init_db()
    for slug in (FIRST, OTHER):
        await database.upsert_tournament(slug, slug, "SF6", "event", "SF6", "{}")
    await database.upsert_active_match(
        "m1", tournament_slug=FIRST, event_id="event", p1_name="Alpha", p2_name="Bravo",
        p1_entrant_id="a", p2_entrant_id="b", status="not_started",
    )
    await database.upsert_active_match(
        "m2", tournament_slug=OTHER, event_id="event", p1_name="Other A", p2_name="Other B",
        p1_entrant_id="oa", p2_entrant_id="ob", status="not_started",
    )


@pytest.mark.asyncio
async def test_creation_is_inert_and_rejection_has_no_effect(proposal_db):
    proposal = await create_action_proposal(tournament_slug=FIRST, action_type="call", match_id="m1", reason="Ready to call")
    assert (await database.get_active_match("m1"))["status"] == "not_started"
    assert await database.get_pending_hub_commands() == []
    rejected = await reject_action_proposal(proposal["id"], reason="TO chose another match")
    assert rejected["approval_status"] == "rejected"
    assert await database.get_pending_hub_commands() == []


@pytest.mark.asyncio
async def test_expiry_untrusted_actor_and_tournament_isolation(proposal_db):
    with pytest.raises(ProposalError):
        await create_action_proposal(tournament_slug=FIRST, action_type="call", match_id="m1", reason="Nope", actor="assistant")
    with pytest.raises(ProposalError):
        await create_action_proposal(tournament_slug=FIRST, action_type="call", match_id="m2", reason="Wrong tournament")
    proposal = await create_action_proposal(tournament_slug=FIRST, action_type="announcement_draft", payload={"text": "Welcome"}, reason="Open doors", expires_in_seconds=60)
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("UPDATE action_proposals SET expires_at=? WHERE id=?", ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), proposal["id"]))
        await db.commit()
    expired = await approve_action_proposal(proposal["id"])
    assert expired["approval_status"] == "expired"
    assert await database.get_pending_hub_commands() == []


@pytest.mark.asyncio
async def test_concurrent_approval_creates_one_executor_command(proposal_db):
    proposal = await create_action_proposal(tournament_slug=FIRST, action_type="call", match_id="m1", reason="Ready")
    left, right = await asyncio.gather(approve_action_proposal(proposal["id"]), approve_action_proposal(proposal["id"]))
    assert left["command_id"] == right["command_id"]
    commands = await database.get_pending_hub_commands()
    assert [(row["command_text"], row["source"]) for row in commands] == [(f"execute_action_proposal {proposal['id']}", "proposal")]


@pytest.mark.asyncio
async def test_changed_match_requires_new_review_before_execution(proposal_db):
    proposal = await create_action_proposal(tournament_slug=FIRST, action_type="call", match_id="m1", reason="Ready")
    await database.update_active_match("m1", p2_name="Changed")
    reviewed = await approve_action_proposal(proposal["id"])
    assert reviewed["approval_status"] == "needs_review"
    assert reviewed["execution_status"] == "blocked"
    assert await database.get_pending_hub_commands() == []


@pytest.mark.asyncio
async def test_call_execution_uses_the_existing_hub_workflow_once(proposal_db):
    proposal = await create_action_proposal(tournament_slug=FIRST, action_type="call", match_id="m1", reason="Ready")
    await approve_action_proposal(proposal["id"])
    executed = await execute_approved_proposal(proposal["id"])
    repeated = await execute_approved_proposal(proposal["id"])
    assert executed["execution_status"] == repeated["execution_status"] == "workflow_started"
    assert (await database.get_active_match("m1"))["status"] == "called"
    commands = await database.get_pending_hub_commands()
    assert [row["source"] for row in commands] == ["proposal", "proposal"]
    assert commands[1]["command_text"] == "call_match m1"


@pytest.mark.asyncio
async def test_change_after_approval_blocks_execution_without_a_second_effect(proposal_db):
    proposal = await create_action_proposal(tournament_slug=FIRST, action_type="call", match_id="m1", reason="Ready")
    await approve_action_proposal(proposal["id"])
    await database.update_active_match("m1", p2_name="Changed after approval")
    result = await execute_approved_proposal(proposal["id"])
    assert result["approval_status"] == "needs_review"
    assert result["execution_status"] == "blocked"
    assert (await database.get_active_match("m1"))["status"] == "not_started"


@pytest.mark.asyncio
async def test_announcement_execution_is_deduplicated_and_never_sends_directly(proposal_db):
    proposal = await create_action_proposal(tournament_slug=FIRST, action_type="announcement_draft", payload={"text": "Bracket begins"}, reason="Opening")
    await approve_action_proposal(proposal["id"])
    first = await execute_approved_proposal(proposal["id"])
    second = await execute_approved_proposal(proposal["id"])
    assert first["execution_status"] == second["execution_status"] == "outbox_queued"
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT event_type, status, COUNT(*) FROM workflow_outbox GROUP BY event_type, status") as cursor:
            rows = await cursor.fetchall()
    assert [(row[0], row[1], row[2]) for row in rows] == [("discord_announcement", "pending", 1)]
