"""Targeted Start.gg activation safety tests.

These tests exercise the real transition path with a provider double: the
coordinator reads one set, the mutation is sent at most once, and a second
targeted read must verify the outcome before Hub state changes.
"""
from __future__ import annotations

import pytest

import backend.core.database as db
import backend.core.match_state as ms
from backend.core.contracts import (
    ProviderSetResult, ProviderSetState, ProviderSnapshotV2, SnapshotScope,
)


WS = "workspace-startgg-preflight"
SLUG = "tournament/startgg-preflight"


class FakeStartGG:
    provider_type = "startgg"

    def __init__(self, snapshots, *, mutation=None):
        self.snapshots = list(snapshots)
        self.mutation = mutation
        self.mutation_calls = 0

    async def fetch_snapshot(self, request):
        assert request.scope is SnapshotScope.SINGLE_MATCH
        assert request.entity_ids == frozenset({"set-1"})
        payload = self.snapshots.pop(0)
        return ProviderSnapshotV2(
            request=request, payload=payload, observed_at="2026-09-11T12:00:00+00:00",
            covered_scopes=frozenset({SnapshotScope.SINGLE_MATCH}),
            covered_entity_ids=frozenset({"set-1"}),
        )

    async def mark_in_progress(self, set_id):
        assert set_id == "set-1"
        self.mutation_calls += 1
        if self.mutation:
            return self.mutation
        return ProviderSetResult(success=True, set_id=set_id, new_state=ProviderSetState.IN_PROGRESS)


@pytest.fixture
async def preflight_db(tmp_path, monkeypatch):
    old = db.DATABASE_DSN
    db.DATABASE_DSN = str(tmp_path / "startgg-preflight.pg")
    await db.init_db()
    await db.upsert_tournament(
        SLUG, "Fixture", "Event", "event-1", "Game", "{}",
        provider_type="startgg", provider_tournament_id=SLUG,
        provider_account_id="integration-1", workspace_id=WS,
    )
    await db.upsert_active_match(
        "set-1", tournament_slug=SLUG, workspace_id=WS, event_id="event-1",
        status="called", hub_status="called", p1_name="A", p2_name="B",
        p1_entrant_id="11", p2_entrant_id="22", bot_enabled=0,
    )
    yield
    db.DATABASE_DSN = old


def _snap(state, entrants=("11", "22")):
    return {"set_id": "set-1", "state": int(state), "entrant_ids": list(entrants)}


@pytest.mark.asyncio
async def test_activation_reads_mutates_once_and_verifies(preflight_db, monkeypatch):
    provider = FakeStartGG([
        _snap(ProviderSetState.CALLED), _snap(ProviderSetState.IN_PROGRESS),
    ])
    monkeypatch.setattr(ms, "get_provider_for_tournament", lambda *a, **k: _async_result(provider))

    result = await ms.transition_match("set-1", "in_progress", workspace_id=WS)

    assert result["ok"] is True
    assert provider.mutation_calls == 1
    assert (await db.get_active_match("set-1", WS))["status"] == "in_progress"
    row = await db.get_active_match("set-1", WS)
    assert row["provider_state_normalized"] == "in_progress"


@pytest.mark.asyncio
async def test_already_in_progress_is_reconciled_without_mutation(preflight_db, monkeypatch):
    provider = FakeStartGG([_snap(ProviderSetState.IN_PROGRESS)])
    monkeypatch.setattr(ms, "get_provider_for_tournament", lambda *a, **k: _async_result(provider))

    result = await ms.transition_match("set-1", "in_progress", workspace_id=WS)

    assert result["ok"] is True
    assert provider.mutation_calls == 0


@pytest.mark.asyncio
async def test_terminal_or_changed_match_is_held_without_mutation(preflight_db, monkeypatch):
    for payload in (_snap(ProviderSetState.COMPLETE), _snap(ProviderSetState.CALLED, ("99", "22"))):
        provider = FakeStartGG([payload])
        monkeypatch.setattr(ms, "get_provider_for_tournament", lambda *a, **k: _async_result(provider))
        result = await ms.transition_match("set-1", "in_progress", workspace_id=WS)
        assert result["sync_status"] == "needs_review"
        assert provider.mutation_calls == 0
        await db.upsert_active_match("set-1", workspace_id=WS, status="called", hub_status="called")


@pytest.mark.asyncio
async def test_provider_rejection_is_explicit_and_does_not_advance(preflight_db, monkeypatch):
    provider = FakeStartGG(
        [_snap(ProviderSetState.CALLED)],
        mutation=ProviderSetResult(
            success=False, set_id="set-1",
            error_message="MarkInProgress: Set is already complete (category=validation)",
            diagnostics={"operation": "MarkInProgress", "category": "validation"},
        ),
    )
    monkeypatch.setattr(ms, "get_provider_for_tournament", lambda *a, **k: _async_result(provider))

    result = await ms.transition_match("set-1", "in_progress", workspace_id=WS)

    assert result["sync_status"] == "needs_review"
    assert "already complete" in result["error"]
    assert (await db.get_active_match("set-1", WS))["status"] == "called"


@pytest.mark.asyncio
async def test_timeout_after_remote_acceptance_is_reconciled_without_resend(preflight_db, monkeypatch):
    provider = FakeStartGG(
        [_snap(ProviderSetState.CALLED), _snap(ProviderSetState.IN_PROGRESS)],
    )

    async def timeout_after_send(_set_id):
        provider.mutation_calls += 1
        raise TimeoutError("response lost after provider accepted mutation")

    provider.mark_in_progress = timeout_after_send
    monkeypatch.setattr(ms, "get_provider_for_tournament", lambda *a, **k: _async_result(provider))

    result = await ms.transition_match("set-1", "in_progress", workspace_id=WS)

    assert result["ok"] is True
    assert provider.mutation_calls == 1
    assert (await db.get_active_match("set-1", WS))["status"] == "in_progress"


@pytest.mark.asyncio
async def test_state_change_between_preflight_and_mutation_is_reviewed(preflight_db, monkeypatch):
    # The provider changes the set to terminal after the preflight read.  A
    # successful mutation response is not enough; postflight must catch it.
    provider = FakeStartGG([
        _snap(ProviderSetState.CALLED), _snap(ProviderSetState.COMPLETE),
    ])
    monkeypatch.setattr(ms, "get_provider_for_tournament", lambda *a, **k: _async_result(provider))

    result = await ms.transition_match("set-1", "in_progress", workspace_id=WS)

    assert result["sync_status"] == "needs_review"
    assert provider.mutation_calls == 1
    assert (await db.get_active_match("set-1", WS))["status"] == "called"


@pytest.mark.asyncio
async def test_snapshot_network_failure_is_review_not_local_advance(preflight_db, monkeypatch):
    class Down:
        provider_type = "startgg"
        async def fetch_snapshot(self, request):
            raise TimeoutError("fixture network failure")
    monkeypatch.setattr(ms, "get_provider_for_tournament", lambda *a, **k: _async_result(Down()))

    result = await ms.transition_match("set-1", "in_progress", workspace_id=WS)

    assert result["sync_status"] == "needs_review"
    assert (await db.get_active_match("set-1", WS))["status"] == "called"


async def _async_result(value):
    return value
