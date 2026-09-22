from __future__ import annotations
from datetime import UTC, datetime
from typing import Any, Optional, List
from backend.core.contracts import (
    ITournamentProvider,
    ProviderTournament, ProviderSet, ProviderSetState, ProviderSetResult,
    ProviderStream,
    ProviderActionKind, ProviderCapabilitiesV2, ProviderCapability,
    ProviderCommandResultV2, ProviderCommandState, ProviderCommandV2,
    ProviderSnapshotRequestV2, ProviderSnapshotV2, SnapshotScope,
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

    def __init__(self, client: Optional[StartGGClient] = None, *, provider_account_id: str | None = None):
        self._client = client or StartGGClient(provider_account_id=provider_account_id)

    @property
    def provider_name(self) -> str:
        return "start.gg"

    @property
    def provider_type(self) -> str:
        return "startgg"

    @property
    def capabilities(self) -> ProviderCapabilitiesV2:
        """Declare upstream capabilities without performing provider I/O."""
        remote = ProviderCapability(ProviderActionKind.REMOTE)
        return ProviderCapabilitiesV2(
            actions={
                "report_score": remote,
                "report_forfeit": remote,
                "reset_match": remote,
                "reopen_match": remote,
                "mark_called": remote,
                "mark_in_progress": remote,
                "assign_stream": remote,
                "remove_stream": ProviderCapability(
                    ProviderActionKind.LOCAL,
                    "Start.gg has no removeStream mutation; legacy behavior is a local no-op.",
                ),
            },
            supports_targeted_match_fetch=True,
            supports_remote_revision=False,
            supports_idempotency=False,
        )

    async def fetch_snapshot(
        self, request: ProviderSnapshotRequestV2
    ) -> ProviderSnapshotV2:
        """Read through existing legacy methods, preserving their GraphQL behavior."""
        if request.provider_type != self.provider_type:
            raise ValueError(f"Start.gg cannot satisfy provider type {request.provider_type!r}")

        observed_at = datetime.now(UTC).isoformat()
        if request.scope is SnapshotScope.SINGLE_MATCH:
            if len(request.entity_ids) != 1:
                raise ValueError("A Start.gg single-match snapshot requires exactly one set ID.")
            set_id = next(iter(request.entity_ids))
            # Keep the upstream ActivityState value separate from the
            # canonical aiTOB state. The legacy fetch_set_state method exposes
            # only the canonical enum, so read the raw client value here.
            provider_state_raw = await self._client.fetch_set_state(set_id)
            state = SGG_STATE_MAP.get(provider_state_raw, ProviderSetState.NOT_STARTED) if provider_state_raw is not None else None
            entrant_ids = await self.fetch_set_entrant_order(set_id)
            return ProviderSnapshotV2(
                request=request,
                payload={
                    "set_id": set_id,
                    "state": int(state) if state is not None else None,
                    "aitob_state_code": int(state) if state is not None else None,
                    "state_source": "aitob",
                    "provider_state_raw": str(provider_state_raw) if provider_state_raw is not None else None,
                    "entrant_ids": entrant_ids,
                },
                observed_at=observed_at,
                covered_scopes=frozenset({SnapshotScope.SINGLE_MATCH}),
                covered_entity_ids=frozenset({set_id}),
            )

        if request.scope in {
            SnapshotScope.ACTIVE_MATCHES,
            SnapshotScope.BRACKET_STRUCTURE,
            SnapshotScope.ADVANCEMENT_NEIGHBORHOOD,
        }:
            sets = await self.fetch_sets(
                request.tournament_id,
                ignore_activity_guard=bool(request.options.get("ignore_activity_guard")),
            )
            return ProviderSnapshotV2(
                request=request,
                payload={"sets": sets},
                observed_at=observed_at,
                covered_scopes=frozenset({request.scope}),
            )

        if request.scope is SnapshotScope.FULL_SNAPSHOT:
            tournament = await self.fetch_tournament(request.tournament_id)
            sets = await self.fetch_sets(
                request.tournament_id,
                ignore_activity_guard=bool(request.options.get("ignore_activity_guard")),
            )
            return ProviderSnapshotV2(
                request=request,
                payload={"tournament": tournament, "sets": sets},
                observed_at=observed_at,
                covered_scopes=frozenset({
                    SnapshotScope.TOURNAMENT_METADATA,
                    SnapshotScope.PARTICIPANTS,
                    SnapshotScope.BRACKET_STRUCTURE,
                    SnapshotScope.ACTIVE_MATCHES,
                    SnapshotScope.FULL_SNAPSHOT,
                }),
            )

        tournament = await self.fetch_tournament(request.tournament_id)
        return ProviderSnapshotV2(
            request=request,
            payload={"tournament": tournament},
            observed_at=observed_at,
            covered_scopes=frozenset({request.scope}),
        )

    async def execute_remote_command(
        self, command: ProviderCommandV2
    ) -> ProviderCommandResultV2:
        """Refuse unleased writes; mutations use the durable command service."""
        return ProviderCommandResultV2(
            command_id=command.command_id,
            state=ProviderCommandState.NEEDS_REVIEW,
            acknowledged=False,
            error_message="Remote commands must be dispatched by the durable command service.",
        )

    async def fetch_tournament(self, slug_or_id: str) -> Optional[ProviderTournament]:
        data = await self._client.query(queries.TOURNAMENT_INFO, {"slug": slug_or_id})
        raw = data.get("tournament")
        if not raw:
            return None
        return map_tournament(raw)

    async def fetch_user_by_slug(self, slug: str) -> dict | None:
        """Provider-specific identity proof used by verified registration."""
        return await self._client.fetch_user_by_slug(slug)

    async def fetch_user_cfn(self, user_id: str, tournament_slugs: list[str]) -> str | None:
        return await self._client.fetch_user_cfn(user_id, tournament_slugs)

    async def fetch_event_game_metadata(self, event_id: str) -> dict[str, Any]:
        """Fetch Start.gg's current character/stage catalog for one Event game."""
        event_key = str(event_id or "").strip()
        if not event_key:
            raise ValueError("event_id_required")
        data = await self._client.query(queries.EVENT_GAME_METADATA, {"eventId": event_key})
        event = (data or {}).get("event") or {}
        videogame = event.get("videogame") or {}

        def catalog_items(value: Any, *, include_images: bool = False) -> list[dict[str, Any]]:
            if not isinstance(value, list):
                return []
            items: list[dict[str, Any]] = []
            for item in value:
                if not isinstance(item, dict) or item.get("id") is None or not item.get("name"):
                    continue
                entry: dict[str, Any] = {"id": str(item["id"]), "name": str(item["name"])}
                if include_images:
                    images = [
                        {
                            key: image.get(key)
                            for key in ("id", "url", "type", "width", "height", "ratio")
                            if image.get(key) is not None
                        }
                        for image in (item.get("images") or [])
                        if isinstance(image, dict) and image.get("url")
                    ]
                    # Keep the legacy catalog shape when the provider has no
                    # artwork for a character; real Start.gg catalogs include
                    # at least one image and receive the additive fields.
                    if images:
                        entry["images"] = images
                        entry["image_url"] = next(
                            (image["url"] for image in images if image.get("type") in ("icon", "profile", "thumbnail")),
                            images[0]["url"],
                        )
                items.append(entry)
            return items

        return {
            "event_id": str(event.get("id") or event_key),
            "event_name": str(event.get("name") or ""),
            "videogame_id": str(videogame.get("id")) if videogame.get("id") is not None else None,
            "game_name": videogame.get("name") or videogame.get("displayName"),
            "characters": catalog_items(videogame.get("characters"), include_images=True),
            "stages": catalog_items(videogame.get("stages")),
        }

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
                map_set(n, event_id=str(ev.get("id") or ""), event_name=ev.get("name") or "")
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
            diagnostics = getattr(self._client, "last_error", None)
            return ProviderSetResult(
                success=False, set_id=set_id, error_message=str(e),
                diagnostics=diagnostics if isinstance(diagnostics, dict) else None,
            )

    async def report_winner_only(self, set_id: str, winner_id: str) -> ProviderSetResult:
        try:
            await self._client.report_set_winner_only(set_id, winner_id)
            return ProviderSetResult(success=True, set_id=set_id, new_state=ProviderSetState.COMPLETE)
        except Exception as e:
            diagnostics = getattr(self._client, "last_error", None)
            return ProviderSetResult(
                success=False, set_id=set_id, error_message=str(e),
                diagnostics=diagnostics if isinstance(diagnostics, dict) else None,
            )

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
        diagnostics = getattr(self._client, "last_error", None)
        if not isinstance(diagnostics, dict):
            diagnostics = None
        detail = None
        if diagnostics:
            operation = diagnostics.get("operation") or "MarkInProgress"
            message = str(diagnostics.get("message") or "Start.gg rejected the mutation")
            category = diagnostics.get("category")
            detail = f"{operation}: {message}"
            if category:
                detail += f" (category={category})"
        return ProviderSetResult(
            success=success, set_id=set_id,
            new_state=ProviderSetState.IN_PROGRESS if success else None,
            error_message=None if success else (detail or "markSetInProgress failed; provider did not accept the transition"),
            diagnostics=diagnostics,
        )

    async def mark_called(self, set_id: str) -> ProviderSetResult:
        """Call a set on start.gg (state -> CALLED), triggering its native check-in wave.

        Spike-verified to fire start.gg's player-facing check-in timer + notifications.
        Best-effort, mirroring mark_in_progress: a preview/non-callable set fails cleanly.
        """
        if str(set_id).startswith("preview"):
            return ProviderSetResult(
                success=False, set_id=set_id,
                error_message="Preview sets cannot be called."
            )
        success = await self._client.mark_called(set_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            new_state=ProviderSetState.CALLED if success else None,
            error_message=None if success else "markSetCalled failed (check token scope / set state)"
        )

    async def start_tournament(self, slug_or_id: str) -> ProviderSetResult:
        return ProviderSetResult(
            success=False,
            set_id=str(slug_or_id),
            error_message="Start.gg does not expose a documented remote tournament-start mutation. Start matches from the Hub when the bracket is ready.",
        )

    async def reset_bracket(
        self,
        slug_or_id: str,
        *,
        event_id: str | None = None,
    ) -> ProviderSetResult:
        """Reset match results for the selected Start.gg event with the API token.

        Start.gg exposes ``resetSet`` rather than a documented tournament-level
        ``resetBracket`` mutation. We find root sets for every phase group and
        reset each root with ``resetDependentSets=true``. This clears match
        results and dependent sets, but does not claim to transition the event
        or phase back to the provider UI's ``CREATED`` state.
        """
        if not event_id:
            return ProviderSetResult(
                success=False,
                set_id=str(slug_or_id),
                error_message="Start.gg bracket reset requires the selected event scope.",
                diagnostics={"operation": "ResetBracket", "category": "missing_scope"},
            )

        try:
            raw_sets = await self._fetch_event_reset_sets(str(event_id))
            if not raw_sets:
                return ProviderSetResult(
                    success=False,
                    set_id=str(slug_or_id),
                    error_message="Start.gg returned no phase-group sets for this event.",
                    diagnostics={"operation": "ResetBracket", "category": "empty_bracket"},
                )

            planned_reset_count = sum(
                1 for item in raw_sets
                if item.get("id") is not None and int(item.get("state") or 1) != 1
            )
            if planned_reset_count == 0:
                return ProviderSetResult(
                    success=True,
                    set_id=str(slug_or_id),
                    new_state=ProviderSetState.NOT_STARTED,
                    diagnostics={
                        "operation": "ResetBracket",
                        "event_id": str(event_id),
                        "root_set_ids": [],
                        "affected_set_count": 0,
                        "affected_phase_group_count": 0,
                        "no_changes": True,
                    },
                )
            # A root set has no entrant source from another set (its slots are
            # seeded directly).  This is intentionally different from the
            # reverse dependency set: the latter identifies leaves, while the
            # provider's ``resetDependentSets`` flag must be sent on roots.
            root_ids = [
                str(item["id"])
                for item in raw_sets
                if item.get("id") is not None
                and not any(
                    isinstance(source, dict)
                    and str(source.get("type") or "").lower() == "set"
                    for source in (item.get("entrant1Source"), item.get("entrant2Source"))
                )
            ]
            if not root_ids:
                # A malformed/incomplete provider graph should not silently
                # reset an arbitrary match.  Keep a deterministic fallback so
                # the provider can still report a useful error if no roots are
                # exposed for this bracket.
                root_ids = [
                    str(item["id"])
                    for item in raw_sets
                    if item.get("id") is not None
                    and int(item.get("state") or 1) != 1
                ]
            if not root_ids:
                return ProviderSetResult(
                    success=True,
                    set_id=str(slug_or_id),
                    new_state=ProviderSetState.NOT_STARTED,
                    diagnostics={
                        "operation": "ResetBracket",
                        "root_set_ids": [],
                        "affected_set_count": 0,
                        "affected_phase_group_count": 0,
                    },
                )

            affected_set_ids: set[str] = set()
            affected_phase_groups = 0
            root_results: list[dict[str, Any]] = []
            for root_id in root_ids:
                data = await self._client.reset_set_with_dependencies(
                    root_id,
                    reset_dependent_sets=True,
                )
                reset_set = (data or {}).get("resetSet") or {}
                reset_data = reset_set.get("resetAffectedData") or {}
                affected_set_ids.add(str(reset_set.get("id") or root_id))
                for affected in reset_data.get("affectedSets") or []:
                    if isinstance(affected, dict) and affected.get("id") is not None:
                        affected_set_ids.add(str(affected["id"]))
                try:
                    affected_phase_groups += int(reset_data.get("affectedPhaseGroupCount") or 0)
                except (TypeError, ValueError):
                    pass
                root_results.append({
                    "root_set_id": root_id,
                    "affected_set_count": (
                        reset_data.get("affectedSetCount")
                        if isinstance(reset_data.get("affectedSetCount"), int)
                        and int(reset_data.get("affectedSetCount")) >= 0
                        else None
                    ),
                })

            return ProviderSetResult(
                success=True,
                set_id=str(slug_or_id),
                new_state=ProviderSetState.NOT_STARTED,
                diagnostics={
                    "operation": "ResetBracket",
                    "event_id": str(event_id),
                    "root_set_ids": root_ids,
                    # Some Start.gg responses use -1 for this field even when
                    # the dependent sets were reset.  Prefer the provider's
                    # explicit affected IDs, then fall back to the planned
                    # non-initial sets so the Hub message remains truthful.
                    "affected_set_count": (
                        0
                        if planned_reset_count == 0
                        else max(len(affected_set_ids), planned_reset_count)
                    ),
                    "affected_phase_group_count": affected_phase_groups,
                    "root_results": root_results,
                },
            )
        except Exception as exc:
            diagnostics = getattr(self._client, "last_error", None)
            return ProviderSetResult(
                success=False,
                set_id=str(slug_or_id),
                error_message=str(exc),
                diagnostics=diagnostics if isinstance(diagnostics, dict) else {
                    "operation": "ResetBracket",
                    "category": "provider_error",
                },
            )

    async def _fetch_event_reset_sets(self, event_id: str) -> list[dict[str, Any]]:
        """Load all sets in the event's phase groups for reset planning."""
        groups_data = await self._client.query(
            queries.EVENT_PHASE_GROUPS,
            {"eventId": str(event_id)},
        )
        event = (groups_data or {}).get("event") or {}
        phase_groups = [
            node
            for phase in event.get("phases") or []
            for node in ((phase.get("phaseGroups") or {}).get("nodes") or [])
            if isinstance(node, dict) and node.get("id") is not None
        ]
        all_sets: list[dict[str, Any]] = []
        for group in phase_groups:
            page = 1
            group_set_count = 0
            while True:
                data = await self._client.query(
                    queries.PHASE_GROUP_RESET_SETS,
                    {
                        "phaseGroupId": str(group["id"]),
                        "page": page,
                        "perPage": 500,
                    },
                )
                connection = ((data or {}).get("phaseGroup") or {}).get("sets") or {}
                nodes = [node for node in (connection.get("nodes") or []) if isinstance(node, dict)]
                all_sets.extend(nodes)
                group_set_count += len(nodes)
                total = int((connection.get("pageInfo") or {}).get("total") or 0)
                if not nodes or group_set_count >= total or len(nodes) < 500:
                    break
                page += 1
        return all_sets

    async def reset_tournament(self, slug_or_id: str) -> ProviderSetResult:
        return ProviderSetResult(
            success=False,
            set_id=str(slug_or_id),
            error_message="Use the selected event's Reset Bracket action for Start.gg.",
        )

    async def mark_dq(self, set_id: str, winner_id: str) -> ProviderSetResult:
        success = await self._client.mark_set_dq(set_id, winner_id)
        return ProviderSetResult(
            success=success, set_id=set_id,
            new_state=ProviderSetState.COMPLETE if success else None
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
