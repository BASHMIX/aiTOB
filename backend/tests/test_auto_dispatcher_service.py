"""Acceptance tests for the deterministic, local-only Auto-Dispatcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.core import database
from backend.core.auto_dispatcher.policy import DispatchPolicy
from backend.core.auto_dispatcher.service import AutoDispatcherService
from backend.api.schemas import PatchTournamentSettingsRequest
from pydantic import ValidationError
from backend.core.storage import dbapi


SLUG = "dispatch/test"
EVENT = "sf6"
NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
async def dispatch_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "dispatcher.pg"))
    await database.init_db()
    await database.upsert_tournament(SLUG, "Dispatch Test", "SF6", EVENT, "SF6", "{}")
    await database.update_tournament_settings(
        SLUG,
        auto_dispatch_enabled=True,
        auto_dispatch_concurrency=1,
        auto_dispatch_stop_at=0,
        auto_dispatch_on_stream=False,
        provider_last_synced_at=NOW.isoformat(),
    )
    await database.set_setting("auto_dispatch_master_switch", "on")
    yield


async def _match(set_id: str, **extra):
    data = {
        "tournament_slug": SLUG,
        "event_id": EVENT,
        "event_name": "SF6",
        "p1_name": "Alpha",
        "p2_name": "Bravo",
        "p1_entrant_id": f"{set_id}-p1",
        "p2_entrant_id": f"{set_id}-p2",
        "p1_discord": "1001",
        "p2_discord": "1002",
        "status": "not_started",
        "bot_enabled": True,
        "match_number": 1,
        "last_successful_snapshot_at": NOW.isoformat(),
    }
    data.update(extra)
    await database.upsert_active_match(set_id, **data)


async def _verified(set_id: str, *, both: bool = True):
    entrant_ids = [f"{set_id}-p1"] + ([f"{set_id}-p2"] if both else [])
    for entrant_id in entrant_ids:
        await database.upsert_provider_identity_link_v2({
            "provider_type": "startgg",
            "tournament_slug": SLUG,
            "provider_entrant_id": entrant_id,
            "discord_user_id": f"discord-{entrant_id}",
            "verification_state": "verified",
            "source": "acceptance_test",
            "verified_at": NOW.isoformat(),
        })


def _policy(tournament: dict, *matches: dict):
    return DispatchPolicy().evaluate(
        tournament=tournament,
        event_id=EVENT,
        matches=matches,
        verified_entrant_ids={str(match.get("p1_entrant_id")) for match in matches} | {str(match.get("p2_entrant_id")) for match in matches},
        now=NOW,
    )


def test_policy_excludes_on_stream_by_default_and_can_be_opted_in():
    tournament = {"slug": SLUG, "auto_dispatch_concurrency": 1, "auto_dispatch_stop_at": 0, "provider_last_synced_at": NOW.isoformat()}
    match = {
        "set_id": "stream", "status": "not_started", "bot_enabled": True, "is_stream_match": True,
        "p1_name": "A", "p2_name": "B", "p1_entrant_id": "p1", "p2_entrant_id": "p2",
        "last_successful_snapshot_at": NOW.isoformat(),
    }

    assert _policy(tournament, match)[0].reason_code == "on_stream_excluded"
    tournament["auto_dispatch_on_stream"] = True
    assert _policy(tournament, match)[0].decision == "select"


def test_policy_records_stale_identity_bye_and_handoff_reasons():
    base = {"slug": SLUG, "auto_dispatch_concurrency": 2, "auto_dispatch_stop_at": 0, "provider_last_synced_at": NOW.isoformat()}
    stale = {"set_id": "stale", "status": "not_started", "bot_enabled": True, "p1_name": "A", "p2_name": "B", "p1_entrant_id": "p1", "p2_entrant_id": "p2", "last_successful_snapshot_at": (NOW - timedelta(seconds=121)).isoformat()}
    unlinked = {"set_id": "unlinked", "status": "not_started", "bot_enabled": True, "p1_name": "A", "p2_name": "B", "p1_entrant_id": "u1", "p2_entrant_id": "u2", "last_successful_snapshot_at": NOW.isoformat()}
    bye = {"set_id": "bye", "status": "not_started", "bot_enabled": True, "p1_name": "A", "p2_name": "Bye", "p1_entrant_id": "b1", "p2_entrant_id": "b2", "last_successful_snapshot_at": NOW.isoformat()}

    reasons = {item.set_id: item.reason_code for item in DispatchPolicy().evaluate(
        tournament=base, event_id=EVENT, matches=[stale, unlinked, bye], verified_entrant_ids={"p1", "p2", "b1", "b2"}, now=NOW,
    )}
    assert reasons == {"stale": "stale_snapshot", "unlinked": "identity_unverified", "bye": "bye"}

    base["auto_dispatch_stop_at"] = 3
    assert _policy(base, stale, unlinked, bye)[0].reason_code == "handoff_threshold"


def test_policy_respects_concurrency_before_selecting_more_matches():
    tournament = {"slug": SLUG, "auto_dispatch_concurrency": 1, "auto_dispatch_stop_at": 0, "provider_last_synced_at": NOW.isoformat()}
    active = {"set_id": "active", "status": "called", "bot_enabled": True}
    candidate = {"set_id": "candidate", "status": "not_started", "bot_enabled": True, "p1_name": "A", "p2_name": "B", "p1_entrant_id": "p1", "p2_entrant_id": "p2", "last_successful_snapshot_at": NOW.isoformat()}
    decision = _policy(tournament, active, candidate)
    assert decision[0].reason_code == "concurrency_reached"


@pytest.mark.asyncio
async def test_service_calls_through_hub_workflow_once_and_deduplicates_decisions(dispatch_db):
    await _match("m1")
    await _verified("m1")
    service = AutoDispatcherService()

    await service.run_once(now=NOW)
    await service.run_once(now=NOW + timedelta(seconds=20))

    assert (await database.get_active_match("m1"))["status"] == "called"
    commands = await database.get_pending_hub_commands()
    assert [(command["command_text"], command["source"]) for command in commands] == [("call_match m1", "dispatcher")]
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT COUNT(*) FROM dispatcher_decisions WHERE set_id='m1' AND reason_code='eligible'") as cursor:
            count = (await cursor.fetchone())[0]
        async with db.execute("SELECT seen_count FROM dispatcher_decisions WHERE set_id='m1' AND reason_code='eligible'") as cursor:
            seen = (await cursor.fetchone())[0]
    # The next tick sees the durable `called` state, so it does not produce a
    # second selection audit or a duplicate Hub command.
    assert (count, seen) == (1, 1)


@pytest.mark.asyncio
async def test_outage_keeps_only_fresh_local_calls_eligible(dispatch_db):
    await database.update_tournament_settings(SLUG, provider_sync_status="error")
    await _match("fresh")
    await _verified("fresh")

    await AutoDispatcherService().run_once(now=NOW)
    assert (await database.get_active_match("fresh"))["status"] == "called"

    await _match("stale", match_number=2, last_successful_snapshot_at=(NOW - timedelta(seconds=121)).isoformat())
    await _verified("stale")
    await AutoDispatcherService().run_once(now=NOW)
    assert (await database.get_active_match("stale"))["status"] == "not_started"


@pytest.mark.asyncio
async def test_repeated_skip_updates_one_audit_record_instead_of_spamming(dispatch_db):
    await _match("stream", is_stream_match=True)
    await _verified("stream")
    service = AutoDispatcherService()

    await service.run_once(now=NOW)
    await service.run_once(now=NOW + timedelta(seconds=20))

    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM dispatcher_decisions "
            "WHERE set_id='stream' AND reason_code='on_stream_excluded'"
        ) as cursor:
            count = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT seen_count FROM dispatcher_decisions "
            "WHERE set_id='stream' AND reason_code='on_stream_excluded'"
        ) as cursor:
            seen = (await cursor.fetchone())[0]
    assert (count, seen) == (1, 2)


@pytest.mark.asyncio
async def test_kill_switch_between_selection_and_execution_prevents_call_and_cancels_only_dispatcher_work(dispatch_db, monkeypatch):
    await _match("m1")
    await _verified("m1")
    original_claim = database.claim_dispatcher_match

    async def disable_after_claim(set_id: str, slug: str) -> bool:
        claimed = await original_claim(set_id, slug)
        await database.set_setting("auto_dispatch_master_switch", "off")
        return claimed

    monkeypatch.setattr(database, "claim_dispatcher_match", disable_after_claim)
    await AutoDispatcherService().run_once(now=NOW)

    assert (await database.get_active_match("m1"))["status"] == "not_started"
    assert await database.get_pending_hub_commands() == []

    await database.add_hub_command("call_match manual", source="manual")
    await database.add_hub_command("call_match automatic", source="dispatcher")
    cancelled = await database.cancel_pending_dispatcher_work()
    assert cancelled >= 1
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT command_text, status FROM hub_commands ORDER BY id") as cursor:
            rows = await cursor.fetchall()
    assert [(row["command_text"], row["status"]) if isinstance(row, dict) else tuple(row) for row in rows] == [
        ("call_match manual", "pending"), ("call_match automatic", "cancelled")
    ]


def test_dispatcher_setting_bounds_are_rejected_by_the_backend_schema():
    with pytest.raises(ValidationError):
        PatchTournamentSettingsRequest(auto_dispatch_concurrency=0)
    with pytest.raises(ValidationError):
        PatchTournamentSettingsRequest(auto_dispatch_concurrency=21)
    with pytest.raises(ValidationError):
        PatchTournamentSettingsRequest(auto_dispatch_stop_at=-1)
    with pytest.raises(ValidationError):
        PatchTournamentSettingsRequest(auto_dispatch_stop_at=65)


@pytest.mark.asyncio
async def test_tournament_disable_between_selection_and_execution_prevents_call(dispatch_db, monkeypatch):
    """The final claim check must respect a TO pausing just this tournament."""
    await _match("m1")
    await _verified("m1")
    original_claim = database.claim_dispatcher_match

    async def disable_tournament_after_claim(set_id: str, slug: str) -> bool:
        claimed = await original_claim(set_id, slug)
        await database.update_tournament_settings(slug, auto_dispatch_enabled=False)
        return claimed

    monkeypatch.setattr(database, "claim_dispatcher_match", disable_tournament_after_claim)
    await AutoDispatcherService().run_once(now=NOW)

    assert (await database.get_active_match("m1"))["status"] == "not_started"
    assert await database.get_pending_hub_commands() == []


@pytest.mark.asyncio
async def test_tournament_pause_cancels_only_its_pending_automatic_work(dispatch_db):
    other_slug = "dispatch/other"
    await database.upsert_tournament(other_slug, "Other", "SF6", EVENT, "SF6", "{}")
    await database.update_tournament_settings(
        SLUG,
        auto_dispatch_enabled=False,
        auto_dispatch_concurrency=2,
        auto_dispatch_stop_at=4,
        auto_dispatch_on_stream=True,
    )
    # Re-opened PostgreSQL rows retain their own settings; another tournament does
    # not inherit the TO's dispatcher choices.
    first = await database.get_tournament(SLUG)
    other = await database.get_tournament(other_slug)
    assert (first["auto_dispatch_enabled"], first["auto_dispatch_concurrency"], first["auto_dispatch_stop_at"], first["auto_dispatch_on_stream"]) == (0, 2, 4, 1)
    assert (other["auto_dispatch_enabled"], other["auto_dispatch_concurrency"], other["auto_dispatch_stop_at"], other["auto_dispatch_on_stream"]) == (0, 1, 8, 0)

    await database.add_hub_command("call_match first", source="dispatcher")
    await database.add_hub_command("call_match second", source="dispatcher")
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.executemany(
            "INSERT INTO dispatcher_dispatch_claims (set_id, tournament_slug, state) VALUES (?, ?, 'queued')",
            [("first", SLUG), ("second", other_slug)],
        )
        await db.commit()

    cancelled = await database.cancel_pending_dispatcher_work(tournament_slug=SLUG)
    assert cancelled == 2  # one command plus one claim, scoped to this tournament
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT command_text, status FROM hub_commands ORDER BY command_text") as cursor:
            commands = await cursor.fetchall()
        async with db.execute("SELECT set_id, state FROM dispatcher_dispatch_claims ORDER BY set_id") as cursor:
            claims = await cursor.fetchall()
    assert [(row["command_text"], row["status"]) if isinstance(row, dict) else tuple(row) for row in commands] == [
        ("call_match first", "cancelled"), ("call_match second", "pending")
    ]
    assert [(row["set_id"], row["state"]) if isinstance(row, dict) else tuple(row) for row in claims] == [
        ("first", "cancelled"), ("second", "queued")
    ]
