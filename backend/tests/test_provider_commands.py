"""Phase 7A durability and idempotency tests for commands and local effects."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from backend.core.storage import dbapi
import pytest

from backend.core import database


async def _resolved(value):
    return value


@pytest.mark.asyncio
async def test_tournament_mutation_is_persisted_before_remote_dispatch(monkeypatch):
    from backend.core.contracts import ProviderSetResult, ProviderSetState
    from backend.core.provider_commands import DurableProviderMutationService

    events: list[tuple[str, str]] = []
    command = {"id": "command-1", "state": "pending", "payload_digest": "unused"}

    async def no_open_command(*_args, **_kwargs):
        return None

    async def create_command(payload):
        events.append(("persist", payload["action"]))
        return command

    async def update_state(command_id, state, **_kwargs):
        events.append((command_id, state))

    async def remote_operation():
        events.append(("remote", "called"))
        return ProviderSetResult(True, "event-1", ProviderSetState.NOT_STARTED)

    monkeypatch.setattr(database, "get_open_provider_command_for_match_v2", no_open_command)
    monkeypatch.setattr(database, "create_provider_command_v2", create_command)
    monkeypatch.setattr(database, "update_provider_command_state_v2", update_state)

    result, command_id = await DurableProviderMutationService(
        workspace_id="workspace-1"
    ).dispatch_tournament(
        tournament={
            "slug": "testfnc",
            "workspace_id": "workspace-1",
            "provider_type": "startgg",
            "provider_account_id": "account-1",
        },
        action="tournament_start",
        payload={"reference": "testfnc"},
        operation=remote_operation,
    )

    assert result.success is True
    assert command_id == "command-1"
    assert events == [
        ("persist", "tournament_start"),
        ("command-1", "sending"),
        ("remote", "called"),
        ("command-1", "acknowledged"),
    ]


@pytest.fixture
async def command_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "commands.pg"))
    await database.init_db()
    await database.upsert_tournament("challonge:account:fnc:1", "FNC", None, None, None, json.dumps({}), provider_type="challonge", provider_tournament_id="1", provider_account_id="account")
    await database.upsert_active_match("challonge:m1", tournament_slug="challonge:account:fnc:1", p1_name="Alpha", p2_name="Bravo", status="in_progress", hub_status="in_progress", station_id="station-a")
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO stations (id, name, active_match_id) VALUES ('station-a', 'Station A', 'challonge:m1')")
        await db.commit()


@pytest.mark.asyncio
async def test_provider_command_state_machine_and_duplicate_fingerprint_are_durable(command_db):
    from backend.core.match_commands import ProviderCommandLifecycle

    lifecycle = ProviderCommandLifecycle()
    command = await lifecycle.create_remote_command(
        match_id="challonge:m1", action="score", payload={"p1_score": 2, "p2_score": 0},
        expected_result={"winner_id": "p1"}, precondition_revision="9",
    )
    same = await lifecycle.create_remote_command(
        match_id="challonge:m1", action="score", payload={"p1_score": 2, "p2_score": 0},
        expected_result={"winner_id": "p1"}, precondition_revision="9",
    )
    await lifecycle.mark(command["id"], "acknowledged")
    await lifecycle.mark(command["id"], "snapshot_verified")
    stored = await database.get_provider_command_v2(command["id"])

    assert same["id"] == command["id"]
    assert stored["state"] == "snapshot_verified"


@pytest.mark.asyncio
async def test_outbox_effect_and_completion_are_idempotent_and_station_safe(command_db):
    from backend.core.completion_service import CompletionService
    from backend.core.workflow_outbox import WorkflowOutboxWorker

    delivered: list[str] = []

    async def dispatch(event):
        delivered.append(event["deduplication_key"])

    await database.enqueue_workflow_outbox_v2({
        "event_id": "call-1", "match_id": "challonge:m1", "event_type": "discord_call",
        "deduplication_key": "call:challonge:m1", "payload": {},
    })
    worker = WorkflowOutboxWorker(dispatch)
    assert await worker.run_once(now="2099-01-01T00:00:00Z") == 1
    assert await worker.run_once(now="2099-01-01T00:01:00Z") == 0
    assert delivered == ["call:challonge:m1"]

    completion = CompletionService()
    first = await completion.complete("challonge:m1", result_kind="score")
    again = await completion.complete("challonge:m1", result_kind="score")
    match = await database.get_active_match("challonge:m1")
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute("SELECT active_match_id FROM stations WHERE id='station-a'") as cursor:
            assert (await cursor.fetchone())[0] is None
        async with db.execute("SELECT COUNT(*) FROM workflow_outbox WHERE match_id='challonge:m1' AND event_type='discord_match_complete'") as cursor:
            assert (await cursor.fetchone())[0] == 1
    assert first["completed"] is True and again["already_complete"] is True
    assert (match["status"], match["hub_status"]) == ("complete", "complete")
    assert match["station_id"] is None


@pytest.mark.asyncio
async def test_completion_repairs_a_partial_legacy_status_without_repeating_effects(command_db):
    from backend.core.completion_service import CompletionService

    await database.upsert_active_match("challonge:m1", status="called", hub_status="complete")

    repaired = await CompletionService().complete(
        "challonge:m1", result_kind="dq", dq_player="p1", p1_score=-1, p2_score=0
    )
    match = await database.get_active_match("challonge:m1")

    assert repaired["completed"] is True
    assert (match["status"], match["hub_status"]) == ("complete", "complete")
    assert (match["p1_score"], match["p2_score"]) == (-1, 0)


@pytest.mark.asyncio
async def test_outbox_retry_runs_the_effect_once_after_a_failure(command_db):
    from backend.core.workflow_outbox import ExternalEffectNotSent, WorkflowOutboxWorker

    attempts = 0
    delivered: list[str] = []

    async def dispatch(event):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ExternalEffectNotSent("Connection refused before delivery")
        delivered.append(event["event_id"])

    await database.enqueue_workflow_outbox_v2({
        "event_id": "retry-1", "match_id": "challonge:m1", "event_type": "discord_call",
        "deduplication_key": "retry:challonge:m1", "payload": {},
    })
    worker = WorkflowOutboxWorker(dispatch)
    assert await worker.run_once(now="2099-01-01T00:00:00Z") == 0
    assert await worker.run_once(now="2099-01-01T00:01:00Z") == 1
    assert delivered == ["retry-1"]


@pytest.mark.asyncio
async def test_score_command_is_preflighted_once_mutated_once_then_verified(command_db, monkeypatch):
    """A repeated submit verifies an uncertain acknowledgement; it never re-sends."""
    from backend.core.contracts import (
        ProviderEntrant, ProviderSet, ProviderSetResult, ProviderSetState,
        ProviderSnapshotV2,
    )
    from backend.core.match_commands import MatchCommandService

    await database.upsert_active_match(
        "challonge:m1", p1_entrant_id="p1", p2_entrant_id="p2", p1_score=2, p2_score=0,
        # Mirrors a live legacy stream row during the additive V2 rollout.
        # The score must reach the durable command path rather than being
        # rejected solely because hub_status has not been backfilled yet.
        provider_set_id="m1", provider_revision="10", status="in_progress", hub_status="not_started",
        last_successful_snapshot_at=None,
    )

    class Provider:
        provider_account_id = "account"
        def __init__(self):
            self.requests = []
            self.mutations = 0
            self.verifications = 0
        async def fetch_snapshot(self, request):
            self.requests.append(request.scope)
            if request.scope.value == "single_match":
                state = ProviderSetState.NOT_STARTED
            else:
                self.verifications += 1
                state = ProviderSetState.NOT_STARTED if self.verifications == 1 else ProviderSetState.COMPLETE
            return ProviderSnapshotV2(
                request=request,
                payload={"sets": [ProviderSet(
                    id="challonge:m1", state=state, provider_set_id="m1",
                    provider_state_raw="complete" if state is ProviderSetState.COMPLETE else "open",
                    entrant1=ProviderEntrant("p1", "Alpha"), entrant2=ProviderEntrant("p2", "Bravo"),
                    winner_id="p1" if state is ProviderSetState.COMPLETE else None,
                    entrant1_score=2 if state is ProviderSetState.COMPLETE else None,
                    entrant2_score=0 if state is ProviderSetState.COMPLETE else None,
                )]},
                observed_at=datetime.now(UTC).isoformat(),
            )
        async def report_score(self, *_args):
            self.mutations += 1
            return ProviderSetResult(True, "challonge:m1", ProviderSetState.COMPLETE)

    provider = Provider()
    service = MatchCommandService(feature_flags={
        "CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true", "CHALLONGE_SCORE_COMMANDS_ENABLED": "true",
    })
    monkeypatch.setattr(service, "_provider_for_match", lambda _match: _resolved(provider))

    first = await service.submit_score("challonge:m1", p1_score=2, p2_score=0)
    # A new service instance represents a restart after acknowledgement and
    # before verification. It finds the durable command and does not resend.
    resumed = MatchCommandService(feature_flags={
        "CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true", "CHALLONGE_SCORE_COMMANDS_ENABLED": "true",
    })
    monkeypatch.setattr(resumed, "_provider_for_match", lambda _match: _resolved(provider))
    second = await resumed.submit_score("challonge:m1", p1_score=2, p2_score=0)

    assert first["outcome"] == "awaiting_verification"
    assert second["outcome"] == "verified"
    assert provider.mutations == 1
    assert [scope.value for scope in provider.requests] == ["single_match", "result_verification", "result_verification"]
    command = await database.get_provider_command_v2(first["command"]["id"])
    assert command["state"] == "snapshot_verified"
    verified_match = await database.get_active_match("challonge:m1")
    assert verified_match["hub_status"] == "complete"
    # A verification snapshot is narrow, but it still owns the provider facts
    # for the one set it contains.  It must not leave the projection at the
    # stale pre-mutation state after a confirmed result.
    assert verified_match["provider_state_raw"] == "complete"
    assert verified_match["provider_state_normalized"] == "complete"


def test_live_legacy_status_remains_eligible_while_additive_hub_status_is_stale():
    """The On-Stream card and command service must agree during migration."""
    from backend.core.match_commands import MatchCommandService

    assert MatchCommandService._effective_workflow_status({
        "status": "in_progress", "hub_status": "not_started",
    }) == "in_progress"


@pytest.mark.asyncio
async def test_verified_snapshot_with_a_different_remote_result_becomes_conflict(command_db, monkeypatch):
    from backend.core.contracts import (
        ProviderEntrant, ProviderSet, ProviderSetResult, ProviderSetState, ProviderSnapshotV2,
    )
    from backend.core.match_commands import MatchCommandError, MatchCommandService

    await database.upsert_active_match(
        "challonge:m1", p1_entrant_id="p1", p2_entrant_id="p2", p1_score=2, p2_score=0,
        provider_set_id="m1", last_successful_snapshot_at=datetime.now(UTC).isoformat(),
    )
    class Provider:
        async def report_score(self, *_args):
            return ProviderSetResult(True, "challonge:m1", ProviderSetState.COMPLETE)
        async def fetch_snapshot(self, request):
            return ProviderSnapshotV2(
                request=request,
                payload={"sets": [ProviderSet(
                    id="challonge:m1", state=ProviderSetState.COMPLETE,
                    entrant1=ProviderEntrant("p1", "Alpha"), entrant2=ProviderEntrant("p2", "Bravo"),
                    winner_id="p2", entrant1_score=0, entrant2_score=2,
                )]}, observed_at=datetime.now(UTC).isoformat(),
            )
    service = MatchCommandService(feature_flags={
        "CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true", "CHALLONGE_SCORE_COMMANDS_ENABLED": "true",
    })
    monkeypatch.setattr(service, "_provider_for_match", lambda _match: _resolved(Provider()))
    with pytest.raises(MatchCommandError, match="conflicts"):
        await service.submit_score("challonge:m1", p1_score=2, p2_score=0)
    command = await database.get_open_provider_command_for_match_v2("challonge:m1", "score")
    assert command is None
    match = await database.get_active_match("challonge:m1")
    assert match["sync_status"] == "conflict"


@pytest.mark.asyncio
async def test_score_preflight_rejects_changed_entrants_without_a_mutation(command_db, monkeypatch):
    from backend.core.contracts import ProviderEntrant, ProviderSet, ProviderSetState, ProviderSnapshotV2
    from backend.core.match_commands import MatchCommandError, MatchCommandService

    await database.upsert_active_match("challonge:m1", p1_entrant_id="p1", p2_entrant_id="p2", provider_set_id="m1")
    class Provider:
        async def fetch_snapshot(self, request):
            return ProviderSnapshotV2(
                request=request,
                payload={"sets": [ProviderSet(
                    id="challonge:m1", state=ProviderSetState.NOT_STARTED,
                    entrant1=ProviderEntrant("p1", "Alpha"), entrant2=ProviderEntrant("replacement", "Replacement"),
                )]},
            )
        async def report_score(self, *_args):
            raise AssertionError("Changed entrants must block the mutation")

    service = MatchCommandService(feature_flags={
        "CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true", "CHALLONGE_SCORE_COMMANDS_ENABLED": "true",
    })
    monkeypatch.setattr(service, "_provider_for_match", lambda _match: _resolved(Provider()))
    with pytest.raises(MatchCommandError, match="changed"):
        await service.submit_score("challonge:m1", p1_score=2, p2_score=0)
    assert (await database.get_active_match("challonge:m1"))["sync_status"] == "needs_review"


@pytest.mark.asyncio
async def test_single_challonge_dq_uses_verified_minus_one_zero_and_never_represents_double_dq(command_db, monkeypatch):
    from backend.core.contracts import ProviderEntrant, ProviderSet, ProviderSetResult, ProviderSetState, ProviderSnapshotV2
    from backend.core.match_commands import MatchCommandError, MatchCommandService

    await database.upsert_active_match(
        "challonge:m1", p1_entrant_id="p1", p2_entrant_id="p2", p1_score=0, p2_score=0,
        provider_set_id="m1", status="in_progress", hub_status="in_progress",
        last_successful_snapshot_at=datetime.now(UTC).isoformat(),
    )

    class Provider:
        def __init__(self):
            self.mutation = None
        async def report_score(self, *args):
            self.mutation = args
            return ProviderSetResult(True, "challonge:m1", ProviderSetState.COMPLETE)
        async def fetch_snapshot(self, request):
            return ProviderSnapshotV2(
                request=request,
                payload={"sets": [ProviderSet(
                    id="challonge:m1", provider_set_id="m1", state=ProviderSetState.COMPLETE,
                    provider_state_raw="complete", entrant1=ProviderEntrant("p1", "Alpha"),
                    entrant2=ProviderEntrant("p2", "Bravo"), winner_id="p2",
                    entrant1_score=-1, entrant2_score=0,
                )]}, observed_at=datetime.now(UTC).isoformat(),
            )

    provider = Provider()
    service = MatchCommandService(feature_flags={
        "CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true", "CHALLONGE_SCORE_COMMANDS_ENABLED": "true",
        "CHALLONGE_DQ_COMMANDS_ENABLED": "true",
    })
    monkeypatch.setattr(service, "_provider_for_match", lambda _match: _resolved(provider))
    outcome = await service.submit_forfeit("challonge:m1", dq_player="p1")
    assert outcome["outcome"] == "verified"
    assert provider.mutation[-2:] == (-1, 0)
    command = await database.get_provider_command_v2(outcome["command"]["id"])
    assert command["action"] == "dq"
    completed = await database.get_active_match("challonge:m1")
    assert completed["result_kind"] == "dq"
    assert completed["dq_player"] == "p1"
    assert (completed["p1_score"], completed["p2_score"]) == (-1, 0)
    with pytest.raises(MatchCommandError, match="Both players"):
        await service.submit_forfeit("challonge:m1", dq_player="both")


def test_reconciliation_emits_decisions_without_running_completion_or_effects():
    from backend.core.reconciliation import reconcile_match_snapshot

    local = {"p1_entrant_id": "p1", "p2_entrant_id": "p2", "hub_status": "in_progress"}
    conflict = reconcile_match_snapshot(local, {**local, "provider_state_raw": "complete", "result": {"winner": "p2"}}, {"expected_result": {"winner": "p1"}})
    changed = reconcile_match_snapshot(local, {**local, "p2_entrant_id": "replacement", "provider_state_raw": "open"})

    assert (conflict.decision, conflict.sync_status.value) == ("CONFLICT", "conflict")
    assert (changed.decision, changed.sync_status.value) == ("INVALIDATE_CALL_FOR_CHANGED_ENTRANTS", "needs_review")
