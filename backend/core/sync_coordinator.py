"""Dark, budget-aware V2 provider-operation coordinator.

The class has no singleton and starts no task on import. A later feature-flagged
service may instantiate it; Phase 2 tests exercise its pure coalescing/admission
behavior only. It deliberately does not import an adapter, Discord, or match state.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import Awaitable, Callable, Mapping

from backend.core.contracts import (
    ProviderSnapshotRequestV2,
    ProviderSnapshotV2,
    SnapshotPriority,
    SnapshotScope,
)


class ProviderBackoffActive(RuntimeError):
    """Raised when an account is paused; force must not bypass this condition."""


class MinimumSyncIntervalActive(RuntimeError):
    """Raised for a non-forced request before the adapter minimum interval expires."""


class ProviderBudgetExhausted(RuntimeError):
    """Raised before I/O when an account's configured request budget is exhausted."""


SnapshotOperation = Callable[[], Awaitable[ProviderSnapshotV2]]


@dataclass
class _InFlightSnapshot:
    request: ProviderSnapshotRequestV2
    future: asyncio.Future[ProviderSnapshotV2]
    covered_scopes: frozenset[SnapshotScope]
    covered_entity_ids: frozenset[str]
    covered_range_keys: frozenset[str]


@dataclass(frozen=True)
class SnapshotTelemetry:
    """An in-memory admission record; persistence remains a repository concern."""

    provider_type: str
    provider_account_id: str
    tournament_id: str
    scope: SnapshotScope
    priority: SnapshotPriority
    disposition: str


def _base_key(request: ProviderSnapshotRequestV2) -> tuple[str, str, str]:
    return (request.provider_type, request.provider_account_id, request.tournament_id)


def _revision_satisfies(candidate: ProviderSnapshotRequestV2, requested: ProviderSnapshotRequestV2) -> bool:
    """Avoid guessing an ordering for opaque provider revisions."""
    if requested.minimum_revision is None:
        return True
    return candidate.minimum_revision == requested.minimum_revision


def request_is_covered_by(
    candidate: ProviderSnapshotRequestV2,
    requested: ProviderSnapshotRequestV2,
    *,
    covered_scopes: frozenset[SnapshotScope] | None = None,
    covered_entity_ids: frozenset[str] | None = None,
    covered_range_keys: frozenset[str] | None = None,
) -> bool:
    """Return whether an in-flight snapshot safely covers a later request.

    Scope names are intentionally insufficient: targeted requests must also be covered
    by the declared entity/range set. This lets an advancement-neighborhood operation
    satisfy its included single-match reads without treating unrelated matches as fresh.
    """
    if _base_key(candidate) != _base_key(requested):
        return False
    if not _revision_satisfies(candidate, requested):
        return False

    scopes = covered_scopes or frozenset({candidate.scope, *candidate.covered_scopes})
    entities = covered_entity_ids if covered_entity_ids is not None else candidate.entity_ids
    scope_matches = (
        candidate.scope == SnapshotScope.FULL_SNAPSHOT
        or requested.scope in scopes
        or candidate.scope == requested.scope
    )
    if not scope_matches:
        return False
    candidate_ranges = covered_range_keys if covered_range_keys is not None else (
        candidate.covered_range_keys | frozenset(
            {candidate.range_key} if candidate.range_key else set()
        )
    )
    if requested.range_key and requested.range_key not in candidate_ranges:
        return False
    # An unbounded request cannot safely join an operation scoped to one or more
    # entities/ranges. FULL_SNAPSHOT is the only universal operation here.
    if (
        candidate.scope != SnapshotScope.FULL_SNAPSHOT
        and not requested.entity_ids
        and requested.range_key is None
        and (entities or candidate_ranges)
    ):
        return False
    if requested.entity_ids and not requested.entity_ids.issubset(entities):
        return False
    return True


class SyncCoordinator:
    """Coordinates provider snapshots without owning provider, workflow, or Discord logic."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._in_flight: dict[tuple[str, str, str], list[_InFlightSnapshot]] = {}
        self._last_completed_at: dict[tuple[str, str, str], float] = {}
        self._backoff_until: dict[tuple[str, str], float] = {}
        self._remaining_budget: dict[tuple[str, str], int | None] = {}
        self.telemetry: list[SnapshotTelemetry] = []
        self._lock = asyncio.Lock()

    def set_backoff(self, provider_type: str, provider_account_id: str, until: float) -> None:
        self._backoff_until[(provider_type, provider_account_id)] = until

    def set_remaining_budget(
        self, provider_type: str, provider_account_id: str, remaining: int | None
    ) -> None:
        """Set a known account budget. ``None`` deliberately means unknown, not zero."""
        if remaining is not None and remaining < 0:
            raise ValueError("remaining budget cannot be negative")
        self._remaining_budget[(provider_type, provider_account_id)] = remaining

    @staticmethod
    def order_requests(
        requests: list[ProviderSnapshotRequestV2],
    ) -> list[ProviderSnapshotRequestV2]:
        """Stable admission order for an explicit caller; no scheduler starts on import."""
        return [
            request
            for _, request in sorted(
                enumerate(requests), key=lambda item: (-int(item[1].priority), item[0])
            )
        ]

    def is_backed_off(self, request: ProviderSnapshotRequestV2) -> bool:
        return self._clock() < self._backoff_until.get(
            (request.provider_type, request.provider_account_id), 0.0
        )

    async def run_snapshot(
        self, request: ProviderSnapshotRequestV2, operation: SnapshotOperation
    ) -> ProviderSnapshotV2:
        """Run or join one covered snapshot operation.

        The coordinator only admits/coalesces an operation. It performs no provider
        I/O itself and schedules no background retry/timer.
        """
        base = _base_key(request)
        future: asyncio.Future[ProviderSnapshotV2]
        async with self._lock:
            for in_flight in self._in_flight.get(base, []):
                if request_is_covered_by(
                    in_flight.request,
                    request,
                    covered_scopes=in_flight.covered_scopes,
                    covered_entity_ids=in_flight.covered_entity_ids,
                    covered_range_keys=in_flight.covered_range_keys,
                ):
                    future = in_flight.future
                    self.telemetry.append(
                        SnapshotTelemetry(
                            request.provider_type, request.provider_account_id,
                            request.tournament_id, request.scope, request.priority, "joined",
                        )
                    )
                    break
            else:
                future = None  # type: ignore[assignment]

            if future is None:
                if self.is_backed_off(request):
                    self.telemetry.append(
                        SnapshotTelemetry(
                            request.provider_type, request.provider_account_id,
                            request.tournament_id, request.scope, request.priority, "backoff_rejected",
                        )
                    )
                    raise ProviderBackoffActive("Provider account backoff is active.")

                budget_key = (request.provider_type, request.provider_account_id)
                remaining = self._remaining_budget.get(budget_key)
                if remaining is not None and remaining <= 0:
                    self.telemetry.append(
                        SnapshotTelemetry(
                            request.provider_type, request.provider_account_id,
                            request.tournament_id, request.scope, request.priority, "budget_rejected",
                        )
                    )
                    raise ProviderBudgetExhausted("Provider account request budget is exhausted.")

                last_completed = self._last_completed_at.get(base)
                if (
                    not request.force
                    and last_completed is not None
                    and request.minimum_interval_seconds > 0
                    and self._clock() - last_completed < request.minimum_interval_seconds
                ):
                    self.telemetry.append(
                        SnapshotTelemetry(
                            request.provider_type, request.provider_account_id,
                            request.tournament_id, request.scope, request.priority, "interval_rejected",
                        )
                    )
                    raise MinimumSyncIntervalActive("Provider minimum sync interval is active.")

                loop = asyncio.get_running_loop()
                future = loop.create_future()
                in_flight = _InFlightSnapshot(
                    request=request,
                    future=future,
                    covered_scopes=frozenset({request.scope, *request.covered_scopes}),
                    covered_entity_ids=request.entity_ids,
                    covered_range_keys=frozenset(
                        {*request.covered_range_keys, *({request.range_key} if request.range_key else set())}
                    ),
                )
                self._in_flight.setdefault(base, []).append(in_flight)
                if remaining is not None:
                    self._remaining_budget[budget_key] = remaining - 1
                self.telemetry.append(
                    SnapshotTelemetry(
                        request.provider_type, request.provider_account_id,
                        request.tournament_id, request.scope, request.priority, "started",
                    )
                )
                asyncio.create_task(self._execute(base, in_flight, operation))
        return await asyncio.shield(future)

    async def _execute(
        self,
        base: tuple[str, str, str],
        in_flight: _InFlightSnapshot,
        operation: SnapshotOperation,
    ) -> None:
        try:
            snapshot = await operation()
            if snapshot.covered_scopes:
                in_flight.covered_scopes = snapshot.covered_scopes
            if snapshot.covered_entity_ids:
                in_flight.covered_entity_ids = snapshot.covered_entity_ids
            if snapshot.covered_range_keys:
                in_flight.covered_range_keys = snapshot.covered_range_keys
            self._last_completed_at[base] = self._clock()
            if not in_flight.future.done():
                in_flight.future.set_result(snapshot)
        except Exception as exc:
            if not in_flight.future.done():
                in_flight.future.set_exception(exc)
        finally:
            async with self._lock:
                active = self._in_flight.get(base, [])
                if in_flight in active:
                    active.remove(in_flight)
                if not active:
                    self._in_flight.pop(base, None)


LiveSync = Callable[[str, str], Awaitable[None]]
TournamentState = Callable[[str], Awaitable[Mapping[str, object] | None]]


class LiveSyncScheduler:
    """One adaptive, cancellable Live loop per tournament.

    It selects the sync *reason* and cadence only. Provider I/O, backoff, and
    reconciliation stay in their existing boundaries. Constructing this class
    creates no task; callers explicitly opt in for a tournament in live mode.
    """

    def __init__(self, sync: LiveSync, get_state: TournamentState, *,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self._sync = sync
        self._get_state = get_state
        self._sleep = sleep
        self._tasks: dict[str, asyncio.Task] = {}
        self._stopping: set[asyncio.Task] = set()
        self.events: list[tuple[str, str, int]] = []

    @staticmethod
    def policy(state: Mapping[str, object]) -> tuple[str | None, int]:
        if state.get("mode") != "live" or state.get("completed") or state.get("archived"):
            return None, 0
        if state.get("pending_verification"):
            return "pending_verification", 300
        if state.get("active_match"):
            return "live_active_match", 300
        if state.get("called_match"):
            return "live_called_match", 300
        return "live_idle", 900

    def start(self, tournament_slug: str) -> bool:
        existing = self._tasks.get(tournament_slug)
        if existing and not existing.done():
            return False
        self._tasks[tournament_slug] = asyncio.create_task(self._run(tournament_slug))
        return True

    def stop(self, tournament_slug: str) -> bool:
        task = self._tasks.pop(tournament_slug, None)
        if task and not task.done():
            self._stopping.add(task)
            task.add_done_callback(self._stopping.discard)
            task.cancel()
            return True
        return False

    async def close(self) -> None:
        for slug in tuple(self._tasks):
            self.stop(slug)
        # Cancellation is a request, not completion. Await database context
        # cleanup, including tasks removed earlier by a Live→Economy switch.
        if self._stopping:
            await asyncio.gather(*tuple(self._stopping), return_exceptions=True)

    async def _run(self, tournament_slug: str) -> None:
        try:
            while True:
                state = await self._get_state(tournament_slug)
                if not state:
                    return
                reason, interval = self.policy(state)
                if not reason:
                    return
                self.events.append((tournament_slug, reason, interval))
                await self._sync(tournament_slug, reason)
                await self._sleep(interval)
        except asyncio.CancelledError:
            raise
        finally:
            task = self._tasks.get(tournament_slug)
            if task is asyncio.current_task():
                self._tasks.pop(tournament_slug, None)
