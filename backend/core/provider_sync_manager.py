"""Rate-aware provider synchronization.

All external bracket reads pass through this module.  It serializes work per
tournament, stores a local snapshot for the dashboard, and coalesces score
bursts into one deferred refresh instead of one fetch per WebSocket update.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from backend.core.contracts import ITournamentProviderV2, ProviderSnapshotRequestV2, SnapshotScope
from backend.core.contracts.tournament_types import ProviderSet
from backend.core.provider_serialization import serialize_provider_set
from backend.core.database import (
    get_tournament,
    save_bracket_snapshot,
    set_tournament_sync_status,
    sync_active_matches,
    apply_challonge_snapshot,
    StaleProviderSnapshotError,
    get_live_sync_state_v2,
    get_tournaments,
)
from backend.core.provider_feature_flags import get_provider_feature_flags
from backend.core.providers.registry import get_provider_for_tournament
from backend.core.sync_coordinator import LiveSyncScheduler, SyncCoordinator


def provider_reference(tournament: dict) -> str:
    remote_id = str(tournament.get("provider_tournament_id") or tournament.get("slug"))
    # Start.gg's GraphQL ``tournament(slug:)`` argument accepts the public
    # slug, not the numeric tournament id stored for provider identity.  Keep
    # the numeric id for ownership/binding, but use the slug for reads and
    # post-reset synchronization.
    if tournament.get("provider_type") == "startgg":
        return str(tournament.get("slug") or remote_id)
    community = tournament.get("provider_subdomain")
    if tournament.get("provider_type") == "challonge" and community:
        return f"{remote_id}@{community}"
    return remote_id


def serialize_set(provider_set: ProviderSet) -> dict[str, Any]:
    """Serialize a provider set without conflating provider and Hub state.

    ``state`` is retained as the legacy, provider-agnostic aiTOB state code.
    New consumers should use ``aitob_state``/``aitob_state_code`` and inspect
    ``provider_state_raw`` when they need the provider's original value.
    No provider credentials or request data are exposed here.
    """
    return serialize_provider_set(provider_set)


class ProviderSyncManager:
    def __init__(self) -> None:
        # Lock scope includes the durable workspace.  A same-named tournament
        # in another tenant must not be serialized behind (or share state with)
        # this tenant's refresh.
        self._locks: dict[tuple[str | None, str], asyncio.Lock] = defaultdict(asyncio.Lock)
        # Deferred and stale-open work is tenant scoped as well as slug scoped.
        # A slug is only unique inside a workspace in the SaaS data model; using
        # it as the in-process key would let one tenant replace another tenant's
        # refresh task.  Keep the legacy string key for deliberately unowned
        # fixtures so existing tests/tools remain compatible during migration.
        self._deferred: dict[str | tuple[str, str], asyncio.Task] = {}
        self._stopping: set[asyncio.Task] = set()
        # Constructed lazily only after both explicit V2 read flags are enabled.
        # Importing this module and normal legacy startup create no coordinator task.
        self._v2_coordinator: SyncCoordinator | None = None
        self._stale_open_tasks: dict[str | tuple[str, str], asyncio.Task] = {}
        self._live_scheduler = LiveSyncScheduler(self._run_live_sync, get_live_sync_state_v2)

    def _get_v2_coordinator(self) -> SyncCoordinator:
        if self._v2_coordinator is None:
            self._v2_coordinator = SyncCoordinator()
        return self._v2_coordinator

    async def _run_live_sync(
        self,
        tournament_slug: str,
        reason: str,
        workspace_id: str | None = None,
    ) -> None:
        # The scheduler stores only a tournament key; resolve its durable
        # workspace before doing any provider work.  This keeps worker context
        # independent from a user session while preventing same-slug tenants
        # from sharing a provider client or projection.
        tournament = await get_tournament(tournament_slug, workspace_id)
        await self.sync_bracket(
            tournament_slug,
            workspace_id=(tournament or {}).get("workspace_id") or workspace_id,
            reason=reason,
        )

    async def restore_live_schedules(self) -> int:
        """Start only explicitly-live Challonge schedules; Economy stays inert."""
        if not get_provider_feature_flags().challonge_read_enabled:
            return 0
        started = 0
        for tournament in await get_tournaments():
            workspace_id = tournament.get("workspace_id")
            # A live worker has no user session to supply tenant context.  Do
            # not let an unowned legacy row fall through to the old unscoped
            # scheduler/provider path; ownership backfill must be explicit.
            if not workspace_id:
                continue
            if tournament.get("provider_type") == "challonge" and tournament.get("challonge_sync_mode") == "live":
                started += int(self._live_scheduler.start(
                    str(tournament["slug"]),
                    workspace_id=workspace_id,
                ))
        return started

    async def configure_live_schedule(self, tournament_slug: str, *, workspace_id: str | None = None) -> bool:
        state = await get_live_sync_state_v2(tournament_slug, workspace_id)
        if not state or state.get("mode") != "live":
            return self._live_scheduler.stop(tournament_slug, workspace_id=workspace_id)
        return self._live_scheduler.start(tournament_slug, workspace_id=workspace_id)

    async def close_live_schedules(self) -> None:
        await self._live_scheduler.close()
        tasks = set(self._deferred.values()) | set(self._stale_open_tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        tasks |= self._stopping
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._deferred.clear()
        self._stale_open_tasks.clear()
        self._stopping.clear()

    async def sync_bracket(
        self,
        tournament_slug: str,
        *,
        workspace_id: str | None = None,
        reason: str = "manual",
        ignore_activity_guard: bool | None = None,
    ) -> dict:
        """Fetch and cache the current provider bracket exactly once per tournament."""
        async with self._locks[(workspace_id, tournament_slug)]:
            tournament = await get_tournament(tournament_slug, workspace_id)
            if not tournament:
                raise ValueError("Tournament not found")
            try:
                trusted_workspace_id = tournament.get("workspace_id") or workspace_id
                flags = get_provider_feature_flags()
                startgg_v2_requested = (
                    tournament.get("provider_type", "startgg") == "startgg"
                    and flags.provider_v2_contracts_enabled
                    and flags.provider_coordinator_enabled
                )
                startgg_account_id = str(tournament.get("provider_account_id") or "")
                # Account-bound V2 reads may never use the historical shared
                # ``default`` bucket.  The unowned fixture compatibility path
                # remains intentionally available until ownership backfill;
                # once a trusted workspace context exists, fail before a
                # provider/client can be constructed or contacted.
                if startgg_v2_requested and trusted_workspace_id is not None and not startgg_account_id:
                    raise ValueError(
                        "Start.gg V2 synchronization requires a tournament-bound integration account."
                    )
                # Preserve the legacy one-argument adapter hook for unscoped
                # fixtures while every owned tournament carries its trusted
                # workspace into provider resolution.
                if trusted_workspace_id is None:
                    provider = await get_provider_for_tournament(tournament_slug)
                else:
                    provider = await get_provider_for_tournament(
                        tournament_slug,
                        trusted_workspace_id,
                    )
                if tournament.get("provider_type") == "challonge":
                    if not flags.challonge_read_enabled:
                        raise ValueError("Challonge read support is not enabled for this Hub.")
                    if not isinstance(provider, ITournamentProviderV2):
                        raise ValueError("Challonge adapter does not support scoped snapshots.")
                    account = str(tournament.get("provider_account_id") or "")
                    if not account:
                        raise ValueError("Challonge tournament is not bound to an integration account.")
                    request = ProviderSnapshotRequestV2(
                        provider_type="challonge", provider_account_id=account,
                        tournament_id=provider_reference(tournament), scope=SnapshotScope.FULL_SNAPSHOT,
                    )
                    snapshot = await self._get_v2_coordinator().run_snapshot(
                        request, lambda: provider.fetch_snapshot_v2(request)
                    )
                    provider_sets = snapshot.payload.get("sets")
                    participants = snapshot.payload.get("participants")
                    if not isinstance(provider_sets, list) or not isinstance(participants, list):
                        raise ValueError("Challonge snapshot was incomplete and was not published.")
                    applied = await apply_challonge_snapshot(
                        tournament_slug, account, provider_sets, participants,
                        scope=request.scope.value, revision=snapshot.revision,
                        observed_at=snapshot.observed_at,
                        covered_scopes={item.value for item in snapshot.covered_scopes},
                        complete_pages=True,
                    )
                    return {**applied, "reason": reason}
                use_v2_reads = (
                    tournament.get("provider_type", "startgg") == "startgg"
                    and startgg_v2_requested
                    and isinstance(provider, ITournamentProviderV2)
                )
                if use_v2_reads:
                    allow_completed_bracket = (
                        bool(tournament.get("ignore_activity_guard"))
                        if ignore_activity_guard is None
                        else bool(ignore_activity_guard)
                    )
                    request = ProviderSnapshotRequestV2(
                        provider_type="startgg",
                        # Legacy unowned fixtures preserve the old V2 contract
                        # value only while their migration is incomplete.  An
                        # owned tournament is rejected above instead of falling
                        # through to this value.
                        provider_account_id=startgg_account_id or "default",
                        tournament_id=provider_reference(tournament),
                        scope=SnapshotScope.ACTIVE_MATCHES,
                        options={
                            "ignore_activity_guard": allow_completed_bracket,
                        },
                    )
                    snapshot = await self._get_v2_coordinator().run_snapshot(
                        request, lambda: provider.fetch_snapshot_v2(request)
                    )
                    provider_sets = snapshot.payload.get("sets")
                    if not isinstance(provider_sets, list) or not all(
                        isinstance(item, ProviderSet) for item in provider_sets
                    ):
                        raise ValueError("Start.gg V2 snapshot returned an invalid sets payload.")
                else:
                    allow_completed_bracket = (
                        bool(tournament.get("ignore_activity_guard"))
                        if ignore_activity_guard is None
                        else bool(ignore_activity_guard)
                    )
                    provider_sets = await provider.fetch_sets(
                        provider_reference(tournament),
                        ignore_activity_guard=allow_completed_bracket,
                    )
                await sync_active_matches(tournament_slug, provider_sets, trusted_workspace_id)
                # Edge-triggered provider CALLED observations share the same
                # durable occurrence ledger as Dashboard calls.  The provider
                # revision (or updated timestamp) is the stable transition
                # version; repeated snapshots and worker restarts are safe.
                if trusted_workspace_id:
                    from backend.core.contracts.tournament_types import ProviderSetState
                    from backend.core.match_commands import record_called_occurrence
                    for observed in provider_sets:
                        if getattr(observed, "state", None) is not ProviderSetState.CALLED:
                            continue
                        version = str(getattr(observed, "provider_revision", None) or getattr(observed, "provider_updated_at", None) or getattr(observed, "provider_state_raw", None) or "called")
                        try:
                            await record_called_occurrence(
                                str(trusted_workspace_id), str(tournament_slug), str(observed.id), version,
                                source="provider_sync", called_at=getattr(observed, "provider_updated_at", None),
                                payload={"provider_revision": version},
                            )
                        except Exception:
                            # A legacy/migrating tournament may not yet have the
                            # occurrence table; the bracket projection remains usable.
                            continue
                serialized = [serialize_set(item) for item in provider_sets]
                if trusted_workspace_id:
                    await save_bracket_snapshot(tournament_slug, serialized, trusted_workspace_id)
                    await set_tournament_sync_status(tournament_slug, True, workspace_id=trusted_workspace_id)
                else:
                    await save_bracket_snapshot(tournament_slug, serialized)
                    await set_tournament_sync_status(tournament_slug, True)
                return {"sets": serialized, "reason": reason}
            except StaleProviderSnapshotError:
                # A newer durable projection remains readable; do not turn a
                # rejected old arrival into a false failed sync.
                raise
            except Exception as exc:
                if workspace_id:
                    await set_tournament_sync_status(
                        tournament_slug, False, str(exc), workspace_id=workspace_id,
                    )
                else:
                    await set_tournament_sync_status(tournament_slug, False, str(exc))
                raise

    async def maybe_sync_on_stale_open(
        self,
        tournament_slug: str,
        *,
        workspace_id: str | None = None,
        ttl_seconds: int = 900,
    ) -> bool:
        """Schedule at most one Economy refresh for a stale Challonge dashboard open.

        This is intentionally not a poller: it returns immediately, creates no timer,
        and repeated renders/Match Card opens join the one in-flight task.
        """
        tournament = await get_tournament(tournament_slug, workspace_id)
        if not tournament or tournament.get("provider_type") != "challonge":
            return False
        if not get_provider_feature_flags().challonge_read_enabled:
            return False
        if not bool(tournament.get("economy_sync_on_stale_open", 1)):
            return False
        last = tournament.get("provider_last_synced_at")
        stale = not last
        if last:
            try:
                stamp = str(last).replace("Z", "+00:00")
                from datetime import UTC, datetime
                from backend.core.timestamps import as_utc
                stale = (datetime.now(UTC) - as_utc(stamp)).total_seconds() > ttl_seconds
            except ValueError:
                stale = True
        if not stale:
            return False
        task_key: str | tuple[str, str] = (
            tournament_slug if workspace_id is None else (workspace_id, tournament_slug)
        )
        task = self._stale_open_tasks.get(task_key)
        if task and not task.done():
            return True

        async def run_once() -> None:
            try:
                trusted_workspace_id = (tournament or {}).get("workspace_id") or workspace_id
                if trusted_workspace_id is None:
                    # Keep the legacy test/tool hook compatible when a fixture
                    # intentionally has no ownership yet.
                    await self.sync_bracket(tournament_slug, reason="stale-on-open")
                else:
                    await self.sync_bracket(
                        tournament_slug,
                        workspace_id=trusted_workspace_id,
                        reason="stale-on-open",
                    )
            except Exception:
                # sync_bracket records a safe error for genuine transport failures.
                pass
            finally:
                if self._stale_open_tasks.get(task_key) is asyncio.current_task():
                    self._stale_open_tasks.pop(task_key, None)

        self._stale_open_tasks[task_key] = asyncio.create_task(run_once())
        return True

    def schedule_bracket_sync(
        self,
        tournament_slug: str,
        *,
        workspace_id: str | None = None,
        delay_seconds: int = 120,
    ) -> None:
        """Coalesce a burst of score reports into one later provider refresh."""
        task_key: str | tuple[str, str] = (
            tournament_slug if workspace_id is None else (workspace_id, tournament_slug)
        )
        old_task = self._deferred.get(task_key)
        if old_task and not old_task.done():
            self._stopping.add(old_task)
            old_task.add_done_callback(self._stopping.discard)
            old_task.cancel()

        async def run() -> None:
            try:
                await asyncio.sleep(delay_seconds)
                await self.sync_bracket(
                    tournament_slug,
                    workspace_id=workspace_id,
                    reason="post-score",
                )
                from backend.api.ws_manager import manager as hub_manager
                from backend.core.database import get_tournament
                tournament = await get_tournament(tournament_slug, workspace_id)
                await hub_manager.broadcast({"type": "match_update", "_workspace_id": (tournament or {}).get("workspace_id")})
            except asyncio.CancelledError:
                pass
            except Exception:
                # sync_bracket records an actionable sync error; do not retry a
                # rate-limited request automatically.
                pass
            finally:
                if self._deferred.get(task_key) is asyncio.current_task():
                    self._deferred.pop(task_key, None)

        self._deferred[task_key] = asyncio.create_task(run())


sync_manager = ProviderSyncManager()
