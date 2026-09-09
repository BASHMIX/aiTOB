"""SQLite-only Organizer Console projection acceptance tests."""
from __future__ import annotations

import pytest

from backend.core import database
from backend.core.action_proposals import approve_action_proposal, create_action_proposal, execute_approved_proposal
from backend.core.organizer_console import read_organizer_console


@pytest.fixture
async def console_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "console.sqlite"))
    await database.init_db()
    for slug in ("console/a", "console/b"):
        await database.upsert_tournament(slug, slug, "SF6", "event", "SF6", "{}")
    await database.update_tournament_settings("console/a", auto_dispatch_enabled=True, auto_dispatch_concurrency=2)
    await database.upsert_active_match("a1", tournament_slug="console/a", event_id="event", p1_name="A", p2_name="B", p1_entrant_id="a", p2_entrant_id="b", status="not_started")
    await database.upsert_active_match("b1", tournament_slug="console/b", event_id="event", p1_name="C", p2_name="D", p1_entrant_id="c", p2_entrant_id="d", status="not_started")


@pytest.mark.asyncio
async def test_console_is_scoped_and_empty_state_is_honest(console_db):
    await database.record_dispatcher_decision(decision_key="a-skip", tournament_slug="console/a", event_id="event", set_id="a1", decision="skip", reason_code="stale_snapshot", explanation="Snapshot is too old")
    await database.record_dispatcher_decision(decision_key="b-skip", tournament_slug="console/b", event_id="event", set_id="b1", decision="skip", reason_code="identity_unverified", explanation="Identity is missing")
    first = await read_organizer_console("console/a")
    second = await read_organizer_console("console/b")
    assert [row["reason_code"] for row in first["dispatch"]["decisions"]] == ["stale_snapshot"]
    assert [row["reason_code"] for row in second["dispatch"]["decisions"]] == ["identity_unverified"]
    assert first["attention"]["conflicts"] == []
    assert first["attention"]["failed_commands"] == []
    assert first["timeline"] == []


@pytest.mark.asyncio
async def test_console_links_proposal_command_and_outbox_without_claiming_delivery(console_db):
    proposal = await create_action_proposal(
        tournament_slug="console/a", action_type="announcement_draft", payload={"text": "Welcome"}, reason="Opening",
    )
    await approve_action_proposal(proposal["id"])
    await execute_approved_proposal(proposal["id"])
    view = await read_organizer_console("console/a")
    assert view["approvals"][0]["execution_status"] == "outbox_queued"
    kinds = {row["kind"] for row in view["timeline"]}
    assert {"proposal", "hub_command", "outbox"}.issubset(kinds)
    outbox = next(row for row in view["timeline"] if row["kind"] == "outbox")
    assert outbox["status"] == "pending"  # queued is not a delivered Discord message
    assert (await read_organizer_console("console/b"))["timeline"] == []


@pytest.mark.asyncio
async def test_console_and_tournament_settings_reject_cross_workspace_reads_and_writes(tmp_path, monkeypatch):
    """Workspace ownership is part of the repository boundary, not only UI filtering."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workspace-console.sqlite"))
    await database.init_db()
    await database.upsert_tournament("tenant/a", "Tenant A", "", "", "", "{}", workspace_id="ws-a")
    await database.upsert_tournament("tenant/b", "Tenant B", "", "", "", "{}", workspace_id="ws-b")
    await database.update_tournament_settings("tenant/a", workspace_id="ws-a", auto_dispatch_enabled=True)
    await database.update_tournament_settings("tenant/a", workspace_id="ws-b", auto_dispatch_enabled=False)
    assert (await database.get_tournament("tenant/a", "ws-a"))["auto_dispatch_enabled"]
    assert (await database.get_tournament("tenant/a", "ws-b")) is None

    await database.upsert_active_match(
        "tenant-a-match", workspace_id="ws-a", tournament_slug="tenant/a",
        p1_name="A", p2_name="B", p1_entrant_id="a", p2_entrant_id="b", status="not_started",
    )
    view = await read_organizer_console("tenant/a", "ws-a")
    assert view["tournament"]["slug"] == "tenant/a"
    with pytest.raises(ValueError, match="Tournament not found"):
        await read_organizer_console("tenant/a", "ws-b")
