"""Provider-safe per-entrant attendance commands."""
from __future__ import annotations

from datetime import UTC, datetime
import asyncio
from typing import Awaitable, Callable

from backend.core import database
from backend.core.contracts import ProviderSetState


class AttendanceCommandError(ValueError):
    """Organizer-facing refusal for an invalid attendance transition."""


class AttendanceCommandService:
    """Coordinate verified attendance with Start.gg's documented set API.

    The same service is intended for authorized manual controls and verified
    Discord self-service. The first confirmed entrant protects the remote set
    from native no-show DQ by moving only the provider axis to IN_PROGRESS.
    The Hub and broadcast axes remain called/queued until both entrants attend.
    """

    def __init__(
        self,
        *,
        workspace_id: str | None = None,
        provider_resolver: Callable[[str, str | None], Awaitable[object]] | None = None,
    ):
        self.workspace_id = workspace_id
        self._provider_resolver = provider_resolver

    async def _provider(self, match: dict):
        if self._provider_resolver:
            return await self._provider_resolver(
                str(match.get("tournament_slug") or ""),
                self.workspace_id or match.get("workspace_id"),
            )
        from backend.core.providers.registry import get_provider_for_tournament
        return await get_provider_for_tournament(
            str(match.get("tournament_slug") or ""),
            self.workspace_id or match.get("workspace_id"),
        )

    @staticmethod
    def _entrant_ids(match: dict) -> tuple[str, str]:
        return str(match.get("p1_entrant_id") or ""), str(match.get("p2_entrant_id") or "")

    async def _fresh_remote_state(self, match: dict, provider) -> ProviderSetState | None:
        expected = {value for value in self._entrant_ids(match) if value}
        actual = {str(value) for value in await provider.fetch_set_entrant_order(str(match["set_id"])) if value}
        if len(expected) != 2 or actual != expected:
            await database.set_match_sync_status_v2(
                str(match["set_id"]), "needs_review",
                reason="Start.gg entrants changed before attendance mutation",
                workspace_id=self.workspace_id or match.get("workspace_id"),
            )
            raise AttendanceCommandError("Start.gg entrants changed; review the match before continuing")
        return await provider.fetch_set_state(str(match["set_id"]))

    async def _protect_present_entrant(self, match: dict) -> dict:
        provider = await self._provider(match)
        state = await self._fresh_remote_state(match, provider)
        if state == ProviderSetState.COMPLETE:
            raise AttendanceCommandError("Start.gg already completed this match")
        if state != ProviderSetState.IN_PROGRESS:
            result = await provider.mark_in_progress(str(match["set_id"]))
            if not result.success:
                # A transport timeout may follow a successful mutation. Re-read
                # once; never blindly resend a lifecycle mutation.
                state = await provider.fetch_set_state(str(match["set_id"]))
                if state != ProviderSetState.IN_PROGRESS:
                    await database.set_match_sync_status_v2(
                        str(match["set_id"]), "needs_review",
                        reason=result.error_message or "Start.gg attendance protection failed",
                        workspace_id=self.workspace_id or match.get("workspace_id"),
                    )
                    raise AttendanceCommandError(
                        result.error_message or "Start.gg did not protect the attending player"
                    )
            else:
                state = await provider.fetch_set_state(str(match["set_id"]))
                if state != ProviderSetState.IN_PROGRESS:
                    raise AttendanceCommandError("Start.gg attendance protection could not be verified")

        now = datetime.now(UTC).isoformat()
        await database.upsert_active_match(
            str(match["set_id"]), workspace_id=self.workspace_id or match.get("workspace_id"),
            provider_state_raw="2", provider_state_normalized="in_progress",
            attendance_protected_at=match.get("attendance_protected_at") or now,
            sync_status="synced", sync_reason="Confirmed entrant protected at Start.gg",
        )
        return await database.get_active_match(
            str(match["set_id"]), self.workspace_id or match.get("workspace_id")
        ) or match

    async def set_attendance(
        self,
        match_id: str,
        *,
        player: str,
        state: str,
        source: str,
    ) -> dict:
        try:
            match = await database.record_startgg_attendance_intent_v2(
                match_id,
                player,
                state,
                source=source,
                workspace_id=self.workspace_id,
            )
        except ValueError as exc:
            raise AttendanceCommandError(str(exc)) from exc
        if state != "present":
            return {"outcome": "local_intent_recorded", "match": match}

        try:
            match = await self._protect_present_entrant(match)
        except AttendanceCommandError:
            raise
        except Exception as exc:
            await database.set_match_sync_status_v2(
                match_id, "needs_review", reason="Start.gg attendance protection unavailable",
                workspace_id=self.workspace_id or match.get("workspace_id"),
            )
            raise AttendanceCommandError(
                "Start.gg is unavailable; attendance was recorded but protection requires review"
            ) from exc

        both_present = (
            match.get("p1_attendance_state") == "present"
            and match.get("p2_attendance_state") == "present"
        )
        if both_present and (match.get("hub_status") or match.get("status")) in {"called", "ready"}:
            from backend.core.match_state import transition_match
            outcome = await transition_match(
                match_id, "in_progress",
                workspace_id=self.workspace_id or match.get("workspace_id"),
                skip_provider=True,
            )
            if outcome.get("error"):
                raise AttendanceCommandError(str(outcome["error"]))
            match = await database.get_active_match(
                match_id, self.workspace_id or match.get("workspace_id")
            ) or match
            return {"outcome": "both_present_started", "match": match}
        return {"outcome": "entrant_protected", "match": match}

    async def resolve_deadline(self, match_id: str) -> dict:
        """Resolve only the verified exactly-one-present Start.gg case.

        Zero present remains provider-owned native no-show handling. Two present
        is already playable. A single present entrant is advanced with the
        documented DQ mutation after a fresh entrant/state preflight.
        """
        match = await database.get_active_match(match_id, self.workspace_id)
        if not match:
            raise AttendanceCommandError("Match not found")
        if (match.get("hub_status") or match.get("status")) not in {"called", "ready"}:
            return {"outcome": "not_called", "match": match}
        present = [
            player for player in ("p1", "p2")
            if match.get(f"{player}_attendance_state") == "present"
        ]
        if len(present) == 0:
            return {"outcome": "provider_double_dq", "match": match}
        if len(present) == 2:
            return {"outcome": "both_present", "match": match}

        provider = await self._provider(match)
        state = await self._fresh_remote_state(match, provider)
        if state == ProviderSetState.COMPLETE:
            return {"outcome": "provider_already_complete", "match": match}
        winner_player = present[0]
        loser_player = "p2" if winner_player == "p1" else "p1"
        winner_id = str(match.get(f"{winner_player}_entrant_id") or "")
        result = await provider.mark_dq(match_id, winner_id)
        verified = await provider.fetch_set_state(match_id)
        if not result.success or verified != ProviderSetState.COMPLETE:
            await database.set_match_sync_status_v2(
                match_id, "needs_review", reason="Start.gg single-attendee DQ could not be verified",
                workspace_id=self.workspace_id or match.get("workspace_id"),
            )
            raise AttendanceCommandError("Start.gg did not verify the single-attendee DQ")

        await database.upsert_active_match(
            match_id, workspace_id=self.workspace_id or match.get("workspace_id"),
            provider_state_raw="3", provider_state_normalized="complete",
            result_kind="dq", dq_player=loser_player, sync_status="synced",
            sync_reason="Start.gg verified single-attendee DQ",
        )
        from backend.core.match_state import transition_match
        outcome = await transition_match(
            match_id, "complete", workspace_id=self.workspace_id or match.get("workspace_id")
        )
        if outcome.get("error"):
            raise AttendanceCommandError(str(outcome["error"]))
        final = await database.get_active_match(
            match_id, self.workspace_id or match.get("workspace_id")
        ) or match
        return {"outcome": "single_attendee_dq_verified", "match": final, "winner_id": winner_id}

    async def reconcile_provider_completion(
        self,
        match_id: str,
        *,
        delays: tuple[float, ...] = (10.0, 20.0),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> dict:
        """Boundedly re-read a provider-owned zero-attendance outcome.

        Start.gg applies its native Double-DQ asynchronously after the mirrored
        deadline. aiTOB never sends a winner for this case; it waits, reads the
        provider truth twice, and only then asks an organizer to review it.
        """
        match = await database.get_active_match(match_id, self.workspace_id)
        if not match:
            raise AttendanceCommandError("Match not found")
        provider = await self._provider(match)
        for delay in delays:
            if delay > 0:
                await sleep(delay)
            current = await database.get_active_match(match_id, self.workspace_id) or match
            if (current.get("hub_status") or current.get("status")) == "complete":
                return {"outcome": "already_reconciled", "match": current}
            try:
                state = await provider.fetch_set_state(match_id)
            except Exception:
                continue
            if state != ProviderSetState.COMPLETE:
                continue
            await database.upsert_active_match(
                match_id, workspace_id=self.workspace_id or match.get("workspace_id"),
                provider_state_raw="3", provider_state_normalized="complete",
                result_kind="double_dq", sync_status="synced",
                sync_reason="Start.gg native zero-attendance outcome reconciled",
            )
            from backend.core.match_state import transition_match
            outcome = await transition_match(
                match_id, "complete", workspace_id=self.workspace_id or match.get("workspace_id")
            )
            if outcome.get("error"):
                raise AttendanceCommandError(str(outcome["error"]))
            final = await database.get_active_match(
                match_id, self.workspace_id or match.get("workspace_id")
            ) or current
            return {"outcome": "provider_double_dq_reconciled", "match": final}

        await database.set_match_sync_status_v2(
            match_id, "needs_review",
            reason="Start.gg did not complete the zero-attendance match after bounded reconciliation",
            workspace_id=self.workspace_id or match.get("workspace_id"),
        )
        return {"outcome": "provider_completion_pending", "match": match}
