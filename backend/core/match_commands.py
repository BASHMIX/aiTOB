"""Feature-gated Hub workflow commands.

Phase 7A deliberately implements only Hub-owned Challonge operations. It never
resolves a provider client, starts a scheduler, or sends a remote mutation.
"""
from __future__ import annotations

import hashlib
import json
import asyncio
from datetime import UTC, datetime
from typing import Mapping
from uuid import uuid4

from backend.core import database
from backend.core.provider_feature_flags import get_provider_feature_flags
from backend.core.contracts import ProviderSetState, ProviderSnapshotRequestV2, SnapshotPriority, SnapshotScope
from backend.core.sync_coordinator import SyncCoordinator


class MatchCommandError(ValueError):
    """Safe organizer-facing refusal for an unavailable or invalid action."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _resolved(value: object) -> bool:
    return bool(str(value or "").strip()) and str(value).strip().lower() not in {"tbd", "unknown", "none"}


class MatchCommandService:
    """Own Hub-local actions while leaving legacy Start.gg paths untouched."""

    def __init__(self, *, feature_flags: Mapping[str, str] | None = None, workspace_id: str | None = None):
        self._flags = get_provider_feature_flags(feature_flags)
        self._workspace_id = workspace_id
        self._verification_tasks: dict[str, asyncio.Task] = {}

    async def _provider_for_match(self, match: dict):
        """Resolve only for explicit, enabled remote result commands.

        Call/Ready/Start/Station never invoke this method. Keeping resolution
        here avoids a hidden provider import in local workflow paths.
        """
        from backend.core.providers.registry import get_provider_for_tournament
        return await get_provider_for_tournament(match["tournament_slug"], self._workspace_id or match.get("workspace_id"))

    async def _local_challonge_match(self, match_id: str) -> dict:
        match = await database.get_active_match(match_id, self._workspace_id)
        if not match:
            raise MatchCommandError("Match not found")
        tournament = await database.get_tournament(match.get("tournament_slug") or "", self._workspace_id or match.get("workspace_id"))
        if not tournament or tournament.get("provider_type") != "challonge":
            raise MatchCommandError("Local Challonge workflow is not enabled for this match")
        if not self._flags.challonge_local_workflow_enabled:
            raise MatchCommandError("Local Challonge workflow is not enabled")
        return match

    @staticmethod
    def _two_sided(match: dict) -> bool:
        return _resolved(match.get("p1_name")) and _resolved(match.get("p2_name"))

    @staticmethod
    def _effective_workflow_status(match: dict) -> str:
        """Bridge an additive hub axis while legacy rows are still in circulation.

        A station could mark an older row ``in_progress`` before the hub_status
        column existed.  That established workflow state must remain usable for
        a result command; otherwise the UI can honestly show a live match but
        the command service rejects its score before creating the ledger entry.
        """
        hub_status = str(match.get("hub_status") or match.get("status") or "not_started")
        legacy_status = str(match.get("status") or "")
        if hub_status in {"not_started", "available"} and legacy_status in {"called", "ready", "in_progress"}:
            return legacy_status
        return hub_status

    async def call(self, match_id: str) -> dict:
        match = await self._local_challonge_match(match_id)
        if not self._two_sided(match):
            raise MatchCommandError("Match needs two resolved entrants before it can be called")
        if (match.get("hub_status") or match.get("status")) not in {"not_started", "available"}:
            raise MatchCommandError("Match is not available to call")
        called_at = _now()
        # Explicit stable-ID links may enrich the local row. Missing links remain
        # missing; no player name is ever used as a Discord-recipient fallback.
        from backend.core.identity_links import resolve_verified_discord_recipient
        recipients = {
            "p1_discord": await resolve_verified_discord_recipient("challonge", match["tournament_slug"], str(match.get("p1_entrant_id") or "")),
            "p2_discord": await resolve_verified_discord_recipient("challonge", match["tournament_slug"], str(match.get("p2_entrant_id") or "")),
        }
        result = await database.apply_local_workflow_transition_v2(
            match_id, "called", "call", fields={
                "called_at": called_at, "p1_ready": False, "p2_ready": False,
                "player1_ready_at": None, "player2_ready_at": None,
                **{key: value for key, value in recipients.items() if value},
            }, effects=[{
                "event_type": "discord_call", "deduplication_key": f"discord_call:{match_id}:{called_at}",
                "payload": {"match_id": match_id, "players": [match.get("p1_entrant_id"), match.get("p2_entrant_id")]},
            }],
        )
        return {"outcome": "local_only", "match": result}

    async def mark_ready(self, match_id: str, player: str) -> dict:
        if player not in {"p1", "p2"}:
            raise MatchCommandError("Player must be p1 or p2")
        match = await self._local_challonge_match(match_id)
        if (match.get("hub_status") or match.get("status")) not in {"called", "ready"}:
            raise MatchCommandError("Only a called match can receive readiness")
        now = _now()
        other = "p2" if player == "p1" else "p1"
        both_ready = bool(match.get(f"{other}_ready"))
        hub_status = "ready" if both_ready else "called"
        result = await database.apply_local_workflow_transition_v2(
            match_id, hub_status, "ready", legacy_status="called", fields={
                f"{player}_ready": True,
                "player1_ready_at" if player == "p1" else "player2_ready_at": now,
            }, effects=[{
                "event_type": "discord_ready", "deduplication_key": f"discord_ready:{match_id}:{player}",
                "payload": {"match_id": match_id, "player": player},
            }],
        )
        return {"outcome": "local_only", "match": result}

    async def start(self, match_id: str) -> dict:
        match = await self._local_challonge_match(match_id)
        if (match.get("hub_status") or match.get("status")) not in {"called", "ready"}:
            raise MatchCommandError("Only a called or ready match can start")
        started_at = _now()
        result = await database.apply_local_workflow_transition_v2(
            match_id, "in_progress", "start", fields={"started_at": started_at}, effects=[{
                "event_type": "obs_match_started", "deduplication_key": f"obs_match_started:{match_id}",
                "payload": {"match_id": match_id},
            }],
        )
        return {"outcome": "local_only", "match": result}

    async def assign_station(self, match_id: str, station_id: str) -> dict:
        match = await self._local_challonge_match(match_id)
        current_hub = match.get("hub_status") or match.get("status") or "not_started"
        # A local Challonge assignment returns before the legacy router's
        # stream-coupling branch.  Keep the Hub projection consistent here:
        # assigning a stream station makes this a featured/on-stream match;
        # assigning an ordinary station explicitly takes it off stream.  This is
        # local workflow metadata only and must not call the provider.
        station = await database.get_station(station_id, self._workspace_id or match.get("workspace_id"))
        if not station:
            raise MatchCommandError("Station was not found")
        try:
            result = await database.apply_local_workflow_transition_v2(
                match_id, current_hub, "assign_station", legacy_status=match.get("status") or current_hub,
                fields={
                    "station_id": station_id,
                    "is_stream_match": bool(station.get("is_stream_station")),
                }, effects=[{
                    "event_type": "obs_station_assigned", "deduplication_key": f"obs_station_assigned:{match_id}:{station_id}",
                    "payload": {"match_id": match_id, "station_id": station_id},
                }],
            )
        except ValueError as exc:
            raise MatchCommandError(str(exc)) from exc
        return {"outcome": "local_only", "match": result}

    async def submit_score(self, match_id: str, *, p1_score: int, p2_score: int,
                           coordinator: SyncCoordinator | None = None,
                           command_action: str = "score", result_kind: str = "score",
                           dq_player: str | None = None) -> dict:
        """Submit one Challonge score and complete only after a verified read.

        The persisted local scores are a draft until this function observes the
        remote winner and points in a result-verification snapshot. Any network
        uncertainty transitions the command to acknowledged/awaiting-verification
        rather than blindly repeating a mutation.
        """
        match = await self._local_challonge_match(match_id)
        if not self._flags.challonge_score_commands_enabled:
            raise MatchCommandError("Challonge score reporting is disabled")
        if command_action == "dq" and not self._flags.challonge_dq_commands_enabled:
            raise MatchCommandError("Challonge manual DQ is disabled")
        if not self._two_sided(match):
            raise MatchCommandError("Match needs two resolved entrants before a score can be sent")
        if int(p1_score) == int(p2_score):
            raise MatchCommandError("Scores cannot be tied")
        if self._effective_workflow_status(match) not in {"in_progress", "ready", "called"}:
            raise MatchCommandError("Match is not eligible for score reporting")

        p1_id, p2_id = str(match.get("p1_entrant_id") or ""), str(match.get("p2_entrant_id") or "")
        if not p1_id or not p2_id:
            raise MatchCommandError("Provider entrant IDs are required before score reporting")
        winner_id = p1_id if int(p1_score) > int(p2_score) else p2_id
        provider = await self._provider_for_match(match)
        expected = {
            "winner_id": winner_id, "entrant1_id": p1_id, "entrant2_id": p2_id,
            "entrant1_score": int(p1_score), "entrant2_score": int(p2_score),
        }

        # A score can only leave the Hub after a stale local view receives one
        # targeted preflight. The coordinator coalesces concurrent attempts for
        # this same match; it owns rate limits, not this service.
        if self._is_stale(match):
            try:
                preflight = await self._targeted_snapshot(match, provider, SnapshotScope.SINGLE_MATCH, coordinator)
            except Exception as exc:
                # Scores already saved in the Hub remain an organizer-visible
                # local draft. Do not send an unsafe mutation while provider
                # freshness is unavailable.
                await database.set_match_sync_status_v2(match_id, "failed", reason="Provider freshness preflight unavailable")
                raise MatchCommandError("Provider is unavailable; result remains a local draft awaiting freshness") from exc
            remote = self._matching_remote_set(preflight, match_id)
            await database.record_targeted_snapshot_observation_v2(
                match_id,
                observed_at=preflight.observed_at,
                revision=preflight.revision,
                provider_state_raw=remote.provider_state_raw if remote else None,
                provider_state=remote.state if remote else None,
            )
            if remote is None or not self._remote_precondition_matches(remote, p1_id, p2_id):
                await database.set_match_sync_status_v2(match_id, "needs_review", reason="Provider entrants or state changed during score preflight")
                raise MatchCommandError("Provider match changed; review it before sending a score")

        lifecycle = ProviderCommandLifecycle(workspace_id=self._workspace_id or match.get("workspace_id"))
        command = await lifecycle.create_remote_command(
            match_id=match_id, action=command_action, payload=expected, expected_result=expected,
            precondition_revision=match.get("provider_revision"),
        )
        if command["state"] == "snapshot_verified":
            from backend.core.completion_service import CompletionService
            completion = await CompletionService().complete(
                match_id,
                result_kind=result_kind,
                dq_player=dq_player,
                p1_score=int(p1_score),
                p2_score=int(p2_score),
            )
            return {"outcome": "already_verified", "command": command, "completion": completion}
        if command["state"] in {"permanent_failure", "conflict", "needs_review"}:
            raise MatchCommandError("This provider result command requires organizer review")
        if command["state"] == "acknowledged":
            return await self._verify_score(match, provider, command, expected, coordinator, result_kind, dq_player)

        await lifecycle.mark(command["id"], "sending")
        try:
            result = await provider.report_score(
                match_id, winner_id, p1_id, p2_id, int(p1_score), int(p2_score)
            )
        except Exception:
            # The provider may have accepted the request before its response was
            # lost. Verification is safe; immediate resend is not.
            await lifecycle.mark(command["id"], "acknowledged", reason="Remote outcome unknown; verification required")
            await database.set_match_sync_status_v2(match_id, "acknowledged_unverified", reason="Remote outcome unknown; awaiting verification")
            return {"outcome": "awaiting_verification", "command": await database.get_provider_command_v2(command["id"])}
        if not result.success:
            await lifecycle.mark(command["id"], "permanent_failure", reason=result.error_message)
            await database.set_match_sync_status_v2(match_id, "failed", reason=result.error_message)
            raise MatchCommandError(result.error_message or "Provider rejected score")
        await lifecycle.mark(command["id"], "acknowledged")
        await database.set_match_sync_status_v2(match_id, "acknowledged_unverified", reason="Result submitted — awaiting provider verification")
        return await self._verify_score(match, provider, command, expected, coordinator, result_kind, dq_player)

    async def submit_forfeit(self, match_id: str, *, dq_player: str,
                             coordinator: SyncCoordinator | None = None) -> dict:
        """Submit one organizer-selected Challonge DQ as the proven 0/-1 score.

        Double-DQ intentionally has no representation: an elimination bracket
        needs one advancing entrant, and aiTOB must not fabricate that choice.
        """
        if dq_player not in {"p1", "p2"}:
            raise MatchCommandError("Both players cannot be DQ'd in Challonge; choose the advancing player manually in Challonge.")
        scores = ("-1", "0") if dq_player == "p1" else ("0", "-1")
        return await self.submit_score(
            match_id, p1_score=int(scores[0]), p2_score=int(scores[1]), coordinator=coordinator,
            command_action="dq", result_kind="dq", dq_player=dq_player,
        )

    @staticmethod
    def _is_stale(match: dict) -> bool:
        stamp = match.get("last_successful_snapshot_at")
        if not stamp:
            return True
        try:
            from backend.core.timestamps import as_utc
            return (datetime.now(UTC) - as_utc(stamp)).total_seconds() > 300
        except (TypeError, ValueError):
            return True

    async def _targeted_snapshot(self, match: dict, provider, scope: SnapshotScope,
                                 coordinator: SyncCoordinator | None):
        tournament = await database.get_tournament(match["tournament_slug"], self._workspace_id or match.get("workspace_id"))
        remote_id = str((tournament or {}).get("provider_tournament_id") or "")
        community = (tournament or {}).get("provider_subdomain")
        reference = f"{remote_id}@{community}" if community else remote_id
        request = ProviderSnapshotRequestV2(
            provider_type="challonge", provider_account_id=str((tournament or {}).get("provider_account_id") or ""),
            tournament_id=reference, scope=scope, entity_ids=frozenset({match["set_id"]}),
            priority=SnapshotPriority.PREFLIGHT_MUTATION,
        )
        gate = coordinator or SyncCoordinator()
        return await gate.run_snapshot(request, lambda: provider.fetch_snapshot_v2(request))

    @staticmethod
    def _matching_remote_set(snapshot, match_id: str):
        return next((item for item in snapshot.payload.get("sets", []) if item.id == match_id), None)

    @staticmethod
    def _remote_precondition_matches(remote, p1_id: str, p2_id: str) -> bool:
        return (
            remote.entrant1 is not None and remote.entrant1.id == p1_id
            and remote.entrant2 is not None and remote.entrant2.id == p2_id
            and remote.state not in {ProviderSetState.COMPLETE, ProviderSetState.INVALID}
        )

    async def _verify_score(self, match: dict, provider, command: dict, expected: dict,
                            coordinator: SyncCoordinator | None, result_kind: str = "score",
                            dq_player: str | None = None) -> dict:
        snapshot = await self._targeted_snapshot(match, provider, SnapshotScope.RESULT_VERIFICATION, coordinator)
        remote = self._matching_remote_set(snapshot, match["set_id"])
        if remote is None:
            await database.set_match_sync_status_v2(match["set_id"], "pending", reason="Verification snapshot did not include the match")
            self._schedule_fast_verification(match["set_id"], provider, command, expected, coordinator, result_kind, dq_player)
            return {"outcome": "awaiting_verification", "command": await database.get_provider_command_v2(command["id"])}
        await database.record_targeted_snapshot_observation_v2(
            match["set_id"],
            observed_at=snapshot.observed_at,
            revision=snapshot.revision,
            provider_state_raw=remote.provider_state_raw,
            provider_state=remote.state,
        )
        actual = {
            "winner_id": remote.winner_id,
            "entrant1_id": remote.entrant1.id if remote.entrant1 else None,
            "entrant2_id": remote.entrant2.id if remote.entrant2 else None,
            "entrant1_score": remote.entrant1_score, "entrant2_score": remote.entrant2_score,
        }
        if remote.state is ProviderSetState.COMPLETE and actual == expected:
            await ProviderCommandLifecycle().mark(command["id"], "snapshot_verified")
            await database.set_match_sync_status_v2(match["set_id"], "synced")
            from backend.core.completion_service import CompletionService
            completion = await CompletionService().complete(
                match["set_id"],
                result_kind=result_kind,
                dq_player=dq_player,
                p1_score=actual["entrant1_score"],
                p2_score=actual["entrant2_score"],
            )
            return {"outcome": "verified", "command": await database.get_provider_command_v2(command["id"]), "completion": completion}
        if remote.state is ProviderSetState.COMPLETE:
            await ProviderCommandLifecycle().mark(command["id"], "conflict", reason="Provider result differs from submitted score")
            await database.set_match_sync_status_v2(match["set_id"], "conflict", reason="Provider result differs from submitted score")
            raise MatchCommandError("Provider result conflicts with the submitted score")
        await database.set_match_sync_status_v2(match["set_id"], "pending", reason="Result submitted — awaiting provider verification")
        self._schedule_fast_verification(match["set_id"], provider, command, expected, coordinator, result_kind, dq_player)
        return {"outcome": "awaiting_verification", "command": await database.get_provider_command_v2(command["id"])}

    def _schedule_fast_verification(self, match_id: str, provider, command: dict, expected: dict,
                                    coordinator: SyncCoordinator | None, result_kind: str = "score",
                                    dq_player: str | None = None) -> None:
        """Queue targeted reads at 5/15/30/60 seconds, never another mutation."""
        current = self._verification_tasks.get(command["id"])
        if current and not current.done():
            return

        async def attempt() -> bool:
            match = await database.get_active_match(match_id, self._workspace_id)
            stored = await database.get_provider_command_v2(command["id"])
            if not match or not stored or stored.get("state") not in {"acknowledged", "sending"}:
                return True
            try:
                result = await self._verify_score(match, provider, stored, expected, coordinator, result_kind, dq_player)
                return result.get("outcome") in {"verified", "already_verified"}
            except MatchCommandError:
                return True

        async def run() -> None:
            from backend.core.provider_commands import ResultVerificationBackoff
            try:
                await ResultVerificationBackoff(attempt, sleep=asyncio.sleep).run()
            finally:
                self._verification_tasks.pop(command["id"], None)

        self._verification_tasks[command["id"]] = asyncio.create_task(run())


class ProviderCommandLifecycle:
    """Ledger-only state helper. Phase 7A never dispatches the stored command."""

    def __init__(self, *, workspace_id: str | None = None):
        self.workspace_id = workspace_id

    async def create_remote_command(
        self, *, match_id: str, action: str, payload: dict, expected_result: dict,
        precondition_revision: str | None,
    ) -> dict:
        match = await database.get_active_match(match_id, self.workspace_id)
        if not match:
            raise MatchCommandError("Match not found")
        tournament = await database.get_tournament(match.get("tournament_slug") or "", self.workspace_id or match.get("workspace_id"))
        if not tournament:
            raise MatchCommandError("Tournament not found")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        open_command = await database.get_open_provider_command_for_match_v2(match_id, action, self.workspace_id or match.get("workspace_id"))
        if open_command:
            if open_command["payload_digest"] == digest:
                return open_command
            raise MatchCommandError("A different provider result command is already awaiting verification")
        key = f"{action}:{match_id}:{precondition_revision or 'none'}:{digest}"
        return await database.create_provider_command_v2({
            "id": str(uuid4()), "tournament_slug": match["tournament_slug"], "set_id": match_id,
            "workspace_id": self.workspace_id or match.get("workspace_id"),
            "provider_type": tournament.get("provider_type") or "startgg",
            "provider_account_id": tournament.get("provider_account_id") or "",
            "action": action, "idempotency_key": key, "payload_digest": digest,
            "expected_result": expected_result, "precondition_revision": precondition_revision,
        })

    async def mark(self, command_id: str, state: str, *, reason: str | None = None) -> dict:
        return await database.update_provider_command_state_v2(command_id, state, reason=reason)


async def record_called_occurrence(
    workspace_id: str,
    tournament_id: str,
    match_id: str,
    occurrence_version: str,
    *,
    source: str,
    called_at: str | None = None,
    payload: Mapping[str, object] | None = None,
) -> dict:
    """Persist one canonical ``CALLED`` occurrence and Discord outbox event."""
    if source not in {"provider_sync", "dashboard"}:
        raise MatchCommandError("invalid_called_source")
    if any(not str(item or "").strip() for item in (workspace_id, tournament_id, match_id, occurrence_version)):
        raise MatchCommandError("called_occurrence_scope_required")
    from backend.core.workflow_outbox import build_call_occurrence_event
    occurred = called_at or _now()
    event = build_call_occurrence_event(
        workspace_id=workspace_id, tournament_id=tournament_id, match_id=match_id,
        occurrence_version=occurrence_version, source_first_observed=source,
        payload=payload,
    )
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = database.aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            row = await (await db.execute(
                "SELECT * FROM match_call_occurrences WHERE workspace_id=? AND tournament_id=? AND match_id=? AND occurrence_version=?" + (" FOR UPDATE" if __import__('backend.core.storage', fromlist=['is_postgres']).is_postgres() else ""),
                (workspace_id, tournament_id, match_id, occurrence_version),
            )).fetchone()
            if row:
                await db.commit()
                return dict(row)
            occurrence_id = str(uuid4())
            await db.execute(
                """INSERT INTO match_call_occurrences
                   (id, workspace_id, tournament_id, match_id, occurrence_version,
                    source_first_observed, called_at, delivery_state, outbox_command_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)""",
                (occurrence_id, workspace_id, tournament_id, match_id, occurrence_version,
                 source, occurred, event["event_id"]),
            )
            await db.execute(
                """INSERT INTO workflow_outbox
                   (event_id, match_id, event_type, payload_json, deduplication_key,
                    status, attempts, next_attempt_at, workspace_id)
                   VALUES (?, ?, ?, ?, ?, 'pending', 0, NULL, ?)
                   ON CONFLICT(deduplication_key) DO NOTHING""",
                (event["event_id"], event["match_id"], event["event_type"],
                 json.dumps(event.get("payload", {}), ensure_ascii=False),
                 event["deduplication_key"], workspace_id),
            )
            await db.commit()
            row = await (await db.execute(
                "SELECT * FROM match_call_occurrences WHERE id=? AND workspace_id=?",
                (occurrence_id, workspace_id),
            )).fetchone()
            return dict(row) if row else {"id": occurrence_id, "delivery_state": "queued"}
        except Exception:
            await db.rollback()
            raise


create_call_occurrence = record_called_occurrence
record_match_called = record_called_occurrence
