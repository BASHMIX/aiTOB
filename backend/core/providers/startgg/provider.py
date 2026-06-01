from __future__ import annotations
from typing import Optional, List
from backend.core.contracts import (
    ITournamentProvider,
    ProviderTournament, ProviderSet, ProviderSetState, ProviderSetResult,
    ProviderStream,
)
from backend.core.providers.startgg import queries
from backend.core.providers.startgg.mapper import map_tournament, map_set, map_stream
from backend.core.providers.startgg.state_map import SGG_STATE_MAP, is_active_state
from backend.core.providers.startgg.client import StartGGClient


class StartGGProvider(ITournamentProvider):
    """start.gg bracket provider.
    
    Wraps the existing StartGGClient and translates all responses
    through the mapper layer into unified contracts.
    """

    def __init__(self, client: Optional[StartGGClient] = None):
        self._client = client or StartGGClient()

    @property
    def provider_name(self) -> str:
        return "start.gg"

    async def fetch_tournament(self, slug_or_id: str) -> Optional[ProviderTournament]:
        data = await self._client.query(queries.TOURNAMENT_INFO, {"slug": slug_or_id})
        raw = data.get("tournament")
        if not raw:
            return None
        return map_tournament(raw)

    async def fetch_sets(
        self,
        slug_or_id: str,
        *,
        ignore_activity_guard: bool = False,
    ) -> List[ProviderSet]:
        """Fetch sets for tournaments with at least one ACTIVE event + phase.

        Query-driven gating — no post-fetch filtering. Activity state is
        normalized via `is_active_state()` because start.gg returns it as int
        for Tournament.state but as enum-name string for Event/Phase.state.

        We deliberately DO NOT gate on `Tournament.state` itself: start.gg
        auto-flips that to COMPLETED when `endAt` passes on the calendar,
        even if brackets have been reset and matches are actively playing.
        The real signal is "is there an ACTIVE phase under an ACTIVE event"
        — if yes, work is happening; if no, there's nothing to fetch.

        When `ignore_activity_guard=True`, the TO has opted to load matches
        from a completed/created tournament for read-only inspection or
        replay testing. ALL phases are queried regardless of state.
        Mutations (Send, DQ) on completed sets still fail at the API level —
        the override is for visibility only.
        """
        # Probe the tournament structure to discover ACTIVE phases.
        state_data = await self._client.query(queries.TOURNAMENT_STATE, {"slug": slug_or_id})
        t = (state_data or {}).get("tournament") or {}

        # Phase IDs — active only by default; ALL when override is on.
        active_phase_ids = [
            str(p["id"])
            for ev in (t.get("events") or []) if ignore_activity_guard or is_active_state(ev.get("state"))
            for p  in (ev.get("phases") or []) if ignore_activity_guard or is_active_state(p.get("state"))
        ]
        if not active_phase_ids:
            return []

        # 3. Paginated sets, natively scoped to those active phases.
        all_sets: List[ProviderSet] = []
        page, per_page = 1, 250
        while True:
            data = await self._client.query(
                queries.TOURNAMENT_SETS,
                {"slug": slug_or_id, "page": page, "perPage": per_page, "phaseIds": active_phase_ids}
            )
            page_sets = [
                map_set(n)
                for ev in ((data or {}).get("tournament") or {}).get("events", []) or []
                for n in ((ev.get("sets") or {}).get("nodes") or [])
            ]
            all_sets.extend(page_sets)
            if len(page_sets) < per_page:
                break
            page += 1

        return all_sets

    async def fetch_set_state(self, set_id: str) -> Optional[ProviderSetState]:
        raw_state = await self._client.fetch_set_state(set_id)
        if raw_state is None:
            return None
        return SGG_STATE_MAP.get(raw_state, ProviderSetState.NOT_STARTED)

    async def fetch_set_entrant_order(self, set_id: str) -> List[str]:
        return await self._client.fetch_set_entrant_order(set_id)

    async def report_score(
        self,
        set_id: str,
        winner_id: str,
        entrant1_id: str,
        entrant2_id: str,
        entrant1_score: int,
        entrant2_score: int,
    ) -> ProviderSetResult:
        try:
            await self._client.report_set_score_normal(
                set_id, winner_id, entrant1_id, entrant2_id,
                entrant1_score, entrant2_score
            )
            return ProviderSetResult(success=True, set_id=set_id, new_state=ProviderSetState.COMPLETE)
        except Exception as e:
            return ProviderSetResult(success=False, set_id=set_id, error_message=str(e))

    async def report_winner_only(self, set_id: str, winner_id: str) -> ProviderSetResult:
        try:
            await self._client.report_set_winner_only(set_id, winner_id)
            return ProviderSetResult(success=True, set_id=set_id, new_state=ProviderSetState.COMPLETE)
        except Exception as e:
            return ProviderSetResult(success=False, set_id=set_id, error_message=str(e))

    async def mark_in_progress(self, set_id: str) -> ProviderSetResult:
        """Activate a set on start.gg (state -> ACTIVE).

        This is the ONLY call needed to put a set live for normal play.
        It does NOT add the set to any stream queue — stream routing is a
        separate mutation pair (assignStream / removeStream) which we never call
        from this code path. Use this for both streamed and non-streamed matches.
        """
        if str(set_id).startswith("preview"):
            return ProviderSetResult(
                success=False, set_id=set_id,
                error_message="Preview sets cannot be activated."
            )
        success = await self._client.mark_in_progress(set_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            new_state=ProviderSetState.IN_PROGRESS if success else None,
            error_message=None if success else "markSetInProgress failed (check token scope / upstream bracket state)"
        )

    async def mark_dq(self, set_id: str, winner_id: str) -> ProviderSetResult:
        success = await self._client.mark_set_dq(set_id, winner_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            new_state=ProviderSetState.COMPLETE if success else None
        )

    async def mark_double_dq(
        self, set_id: str, entrant1_id: str, entrant2_id: str
    ) -> ProviderSetResult:
        """Resolve a double no-show on start.gg.

        start.gg's reportBracketSet requires a winnerId — there is no single-call
        mutation that DQs both slots. To keep the bracket from stalling we resolve
        the set by DQ-ing entrant2 (entrant1 advances as the technical winner). The
        caller records BOTH as DQ locally and warns the TO so the advanced slot can
        be handled upstream if that player also no-shows.
        """
        success = await self._client.mark_set_double_dq(set_id, entrant1_id, entrant2_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            new_state=ProviderSetState.COMPLETE if success else None,
            error_message=None if success else "double DQ failed on start.gg"
        )

    async def reset_set(self, set_id: str) -> ProviderSetResult:
        success = await self._client.reset_set(set_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            new_state=ProviderSetState.NOT_STARTED if success else None
        )

    # ── Streams ────────────────────────────────────────────────────────

    async def fetch_streams(self, slug_or_id: str) -> List[ProviderStream]:
        """Fetch streams configured on the start.gg tournament admin page."""
        raw = await self._client.fetch_streams(slug_or_id)
        return [s for s in (map_stream(r) for r in raw) if s]

    async def assign_stream(self, set_id: str, stream_id: str) -> ProviderSetResult:
        """Push a set onto a start.gg public stream queue (best effort)."""
        success = await self._client.assign_stream(set_id, stream_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            error_message=None if success else
                "assignStream failed (token T.O. scope, stream not configured, or set not ready)"
        )

    async def remove_stream(self, set_id: str) -> ProviderSetResult:
        """Pull a set off a start.gg public stream queue (best effort)."""
        success = await self._client.remove_stream(set_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            error_message=None if success else "removeStream failed"
        )

    async def close(self) -> None:
        await self._client.close()
