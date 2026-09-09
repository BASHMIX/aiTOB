import asyncio

import pytest


@pytest.mark.asyncio
async def test_scheduler_close_awaits_cleanup_of_previously_stopped_task():
    from backend.core.sync_coordinator import LiveSyncScheduler
    started, cleanup_started, release, cleaned = (asyncio.Event() for _ in range(4))
    async def state(_slug):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cleanup_started.set()
            await release.wait()
            cleaned.set()
    async def sync(*args):
        raise AssertionError("no sync expected")
    scheduler = LiveSyncScheduler(sync, state)
    scheduler.start("test")
    await started.wait()
    scheduler.stop("test")
    await cleanup_started.wait()
    closing = asyncio.create_task(scheduler.close())
    await asyncio.sleep(0.01)
    try:
        assert not closing.done()
    finally:
        release.set()
    await closing
    assert cleaned.is_set()

from backend.core.contracts import (
    ProviderSnapshotRequestV2,
    ProviderSnapshotV2,
    SnapshotPriority,
    SnapshotScope,
)
from backend.core.sync_coordinator import (
    MinimumSyncIntervalActive,
    ProviderBudgetExhausted,
    ProviderBackoffActive,
    SyncCoordinator,
    request_is_covered_by,
)


def _request(
    scope: SnapshotScope,
    *,
    entities: set[str] | None = None,
    covered: set[SnapshotScope] | None = None,
    range_key: str | None = None,
    covered_ranges: set[str] | None = None,
    provider: str = "challonge",
    account: str = "account-a",
    minimum_interval_seconds: int = 0,
    force: bool = False,
) -> ProviderSnapshotRequestV2:
    return ProviderSnapshotRequestV2(
        provider_type=provider,
        provider_account_id=account,
        tournament_id="tournament-1",
        scope=scope,
        entity_ids=frozenset(entities or set()),
        covered_scopes=frozenset(covered or set()),
        range_key=range_key,
        covered_range_keys=frozenset(covered_ranges or set()),
        minimum_interval_seconds=minimum_interval_seconds,
        force=force,
    )


def test_scope_containment_requires_entity_coverage_not_only_scope_name():
    neighborhood = _request(
        SnapshotScope.ADVANCEMENT_NEIGHBORHOOD,
        entities={"match-1", "match-2"},
        covered={SnapshotScope.SINGLE_MATCH},
    )

    assert request_is_covered_by(neighborhood, _request(SnapshotScope.SINGLE_MATCH, entities={"match-1"}))
    assert not request_is_covered_by(neighborhood, _request(SnapshotScope.SINGLE_MATCH, entities={"match-3"}))


def test_scope_containment_rejects_an_uncovered_range_even_when_scope_matches():
    candidate = _request(
        SnapshotScope.ADVANCEMENT_NEIGHBORHOOD,
        covered={SnapshotScope.SINGLE_MATCH},
        covered_ranges={"round:winners-1"},
    )

    assert request_is_covered_by(
        candidate,
        _request(SnapshotScope.SINGLE_MATCH, range_key="round:winners-1"),
    )
    assert not request_is_covered_by(
        candidate,
        _request(SnapshotScope.SINGLE_MATCH, range_key="round:winners-2"),
    )


@pytest.mark.asyncio
async def test_compatible_concurrent_requests_coalesce_to_one_operation():
    coordinator = SyncCoordinator()
    request = _request(SnapshotScope.ACTIVE_MATCHES)
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def operation() -> ProviderSnapshotV2:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return ProviderSnapshotV2(request=request, payload={})

    first = asyncio.create_task(coordinator.run_snapshot(request, operation))
    await started.wait()
    second = asyncio.create_task(coordinator.run_snapshot(request, operation))
    release.set()
    await asyncio.gather(first, second)

    assert calls == 1
    assert [entry.disposition for entry in coordinator.telemetry] == ["started", "joined"]


@pytest.mark.asyncio
async def test_provider_backoff_isolated_by_provider_and_account_and_force_cannot_bypass():
    clock = lambda: 100.0
    coordinator = SyncCoordinator(clock=clock)
    blocked = _request(SnapshotScope.SINGLE_MATCH, entities={"match-1"})
    coordinator.set_backoff("challonge", "account-a", 200.0)

    async def operation() -> ProviderSnapshotV2:
        return ProviderSnapshotV2(request=blocked, payload={})

    with pytest.raises(ProviderBackoffActive):
        await coordinator.run_snapshot(blocked, operation)
    with pytest.raises(ProviderBackoffActive):
        await coordinator.run_snapshot(
            _request(SnapshotScope.SINGLE_MATCH, entities={"match-1"}, force=True), operation
        )

    startgg = _request(SnapshotScope.SINGLE_MATCH, entities={"match-1"}, provider="startgg")
    result = await coordinator.run_snapshot(
        startgg, lambda: asyncio.sleep(0, result=ProviderSnapshotV2(request=startgg, payload={}))
    )
    assert result.request.provider_type == "startgg"


@pytest.mark.asyncio
async def test_minimum_interval_blocks_normal_request_but_not_authorized_force():
    now = [100.0]
    coordinator = SyncCoordinator(clock=lambda: now[0])
    request = _request(SnapshotScope.ACTIVE_MATCHES, minimum_interval_seconds=60)

    async def operation() -> ProviderSnapshotV2:
        return ProviderSnapshotV2(request=request, payload={})

    await coordinator.run_snapshot(request, operation)
    with pytest.raises(MinimumSyncIntervalActive):
        await coordinator.run_snapshot(request, operation)
    forced = _request(SnapshotScope.ACTIVE_MATCHES, minimum_interval_seconds=60, force=True)
    await coordinator.run_snapshot(forced, lambda: asyncio.sleep(0, result=ProviderSnapshotV2(request=forced, payload={})))


def test_priority_order_is_stable_and_does_not_require_a_scheduler_worker():
    low = _request(SnapshotScope.PARTICIPANTS)
    high = _request(SnapshotScope.SINGLE_MATCH, entities={"match-1"})
    high = ProviderSnapshotRequestV2(**{**high.__dict__, "priority": SnapshotPriority.PREFLIGHT_MUTATION})

    assert SyncCoordinator.order_requests([low, high]) == [high, low]


@pytest.mark.asyncio
async def test_force_cannot_bypass_a_known_provider_account_budget():
    coordinator = SyncCoordinator()
    request = _request(SnapshotScope.SINGLE_MATCH, entities={"match-1"}, force=True)
    coordinator.set_remaining_budget("challonge", "account-a", 0)

    with pytest.raises(ProviderBudgetExhausted):
        await coordinator.run_snapshot(
            request, lambda: asyncio.sleep(0, result=ProviderSnapshotV2(request=request, payload={}))
        )
