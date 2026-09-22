import asyncio
import random
import datetime
from backend.core.providers.registry import get_provider_for_tournament
from backend.core.database import get_active_match, upsert_active_match, update_active_match, add_bot_feed
from backend.api.ws_manager import manager as hub_mgr
from backend.core.provider_feature_flags import get_provider_feature_flags
from backend.core.contracts import (
    ProviderSetState, ProviderSnapshotRequestV2, SnapshotPriority, SnapshotScope,
)
from backend.core.sync_coordinator import SyncCoordinator

import json
import os

VALID_TRANSITIONS = {
    "not_started": ["called"],
    "called":       ["in_progress", "complete", "not_started"],
    "in_progress":  ["complete", "conflict", "not_started"],
    "conflict":     ["complete", "not_started"],
    "complete":     ["not_started"],
}

def load_workflow_transitions():
    global VALID_TRANSITIONS
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        json_path = os.path.join(root_dir, "docs", "workflows.json")
        
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                match_workflow = data.get("match_workflow", {})
                states = match_workflow.get("states", {})
                
                new_transitions = {}
                for state, config in states.items():
                    # Overlay states (e.g. on_stream) are derived views for docs/UI only —
                    # not real transition nodes, so keep them out of VALID_TRANSITIONS.
                    if config.get("overlay"):
                        continue
                    new_transitions[state] = config.get("allowed_next", [])
                
                if new_transitions:
                    VALID_TRANSITIONS = new_transitions
    except Exception as e:
        print(f"Warning: Failed to load workflow configuration from docs/workflows.json: {e}")

# Overlay states (e.g. `on_stream`) are DERIVED VIEWS of a real state, not
# transition targets — see workflows.json. We load them separately so their
# side-effects (e.g. binding a stream station) can be realized at the exact
# transition the JSON says they derive from, without ever inventing a new state.
WORKFLOW_OVERLAYS: dict = {}

def load_workflow_overlays():
    global WORKFLOW_OVERLAYS
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        json_path = os.path.join(root_dir, "docs", "workflows.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                states = data.get("match_workflow", {}).get("states", {})
                WORKFLOW_OVERLAYS = {
                    name: cfg for name, cfg in states.items() if cfg.get("overlay")
                }
    except Exception as e:
        print(f"Warning: Failed to load workflow overlays from docs/workflows.json: {e}")

# Initial load
load_workflow_transitions()
load_workflow_overlays()

def validate_transition(from_status: str, to_status: str) -> bool:
    allowed = VALID_TRANSITIONS.get(from_status, [])
    return to_status in allowed

def _overlay_condition_holds(condition: str, match: dict) -> bool:
    """Evaluate a simple workflows.json overlay condition against a match row.

    Supports the `<field> == true|false` form used by the `on_stream` overlay
    (condition: "is_stream_match == true"). Anything else is treated as not met,
    keeping behavior strictly bounded to what the JSON declares."""
    try:
        field, op, val = condition.partition("==")
        if not op:
            return False
        field = field.strip()
        want = val.strip().lower() == "true"
        return bool(match.get(field)) == want
    except Exception:
        return False

async def _realize_in_progress_overlays(match: dict, update_kwargs: dict) -> None:
    """Apply side-effects for any overlay the JSON derives from `in_progress`.

    Today that's `on_stream`: when its condition holds and no station is bound
    yet, bind an idle Event-matching stream station at this exact transition.
    If none is free the match still proceeds (the transition is never blocked) —
    the TO can place it via the manual override once a station frees up."""
    set_id = match.get("set_id")
    for name, overlay in WORKFLOW_OVERLAYS.items():
        if overlay.get("derived_from") != "in_progress":
            continue
        if not _overlay_condition_holds(overlay.get("condition", ""), match):
            continue
        if name == "on_stream":
            from backend.core.database import get_available_stream_station, get_station
            station = (
                await get_station(match.get("station_id"), match.get("workspace_id"))
                if match.get("station_id")
                else await get_available_stream_station(
                    match.get("event_id") or "", match.get("workspace_id")
                )
            )
            if station:
                update_kwargs["station_id"] = station["id"]
                route_verified = True
                stream_id = station.get("startgg_stream_id")
                if stream_id:
                    try:
                        provider = await get_provider_for_tournament(
                            match.get("tournament_slug") or "", match.get("workspace_id")
                        )
                        from backend.core.provider_commands import DurableProviderMutationService
                        stream_result = await DurableProviderMutationService(
                            workspace_id=str(match.get("workspace_id") or "")
                        ).dispatch(
                            match_id=str(set_id), action="assign_stream",
                            payload={"stream_id": str(stream_id)},
                            operation=lambda: provider.assign_stream(str(set_id), str(stream_id)),
                            precondition_revision=match.get("provider_revision"),
                        )
                        route_verified = bool(stream_result.success)
                    except Exception as exc:
                        route_verified = False
                        await add_bot_feed(
                            f"📺 Stream assignment failed for {set_id}: {str(exc)[:240]}", "warn",
                            workspace_id=match.get("workspace_id"),
                        )
                # Broadcast is a Hub-owned axis.  Once a stream station is
                # bound to an in-progress match, its OBS projection is live
                # even if Start.gg's optional public stream-queue mutation is
                # awaiting reconciliation.  The provider mutation remains
                # durable and visible through its command state, but must not
                # hide a real local broadcast from the On-Stream panel.
                update_kwargs["broadcast_state"] = "live"
                update_kwargs["broadcast_started_at"] = datetime.datetime.now(datetime.UTC).isoformat()
                if not route_verified:
                    await add_bot_feed(
                        f"📺 Local broadcast is live for {set_id}; Start.gg stream queue is awaiting reconciliation.",
                        "warn", workspace_id=match.get("workspace_id"),
                    )
                await add_bot_feed(
                    f"📺 On-stream: bound {station.get('name') or station['id']} to "
                    f"{match.get('p1_name')} vs {match.get('p2_name')}.", "info"
                )
            else:
                await add_bot_feed(
                    f"📺 {match.get('p1_name')} vs {match.get('p2_name')} is on stream but no "
                    f"free stream station for its event — proceeding unbound; TO to place it.",
                    "warn"
                )


async def _startgg_targeted_snapshot(match: dict, provider):
    """Read and persist only the target Start.gg set before/after a mutation.

    The provider account and workspace come from the stored tournament row, not
    request input.  This deliberately uses the existing SyncCoordinator and
    targeted V2 read contract; it never refreshes the whole tournament.
    """
    from backend.core.database import get_tournament, record_targeted_snapshot_observation_v2
    tournament = await get_tournament(
        match.get("tournament_slug") or "", match.get("workspace_id")
    )
    if not tournament or tournament.get("provider_type") != "startgg":
        return None
    account_id = str(tournament.get("provider_account_id") or "")
    tournament_id = str(tournament.get("provider_tournament_id") or "")
    if not account_id or not tournament_id:
        raise RuntimeError("Start.gg integration account or tournament identity is missing")
    request = ProviderSnapshotRequestV2(
        provider_type="startgg",
        provider_account_id=account_id,
        tournament_id=tournament_id,
        scope=SnapshotScope.SINGLE_MATCH,
        entity_ids=frozenset({str(match["set_id"])}),
        priority=SnapshotPriority.PREFLIGHT_MUTATION,
        force=True,
    )
    snapshot = await SyncCoordinator().run_snapshot(
        request, lambda: provider.fetch_snapshot(request)
    )
    payload = dict(snapshot.payload or {})
    raw_state = payload.get("state")
    try:
        state = ProviderSetState(int(raw_state)) if raw_state is not None else None
    except (TypeError, ValueError):
        state = None
    await record_targeted_snapshot_observation_v2(
        str(match["set_id"]), observed_at=snapshot.observed_at,
        revision=snapshot.revision, provider_state_raw=str(raw_state) if raw_state is not None else None,
        provider_state=state, workspace_id=match.get("workspace_id"),
    )
    return {
        "state": state,
        "raw_state": raw_state,
        "entrant_ids": [str(value) for value in (payload.get("entrant_ids") or [])],
        "snapshot": snapshot,
    }


def _startgg_precondition_matches(match: dict, snapshot: dict) -> bool:
    expected = {str(match.get("p1_entrant_id") or ""), str(match.get("p2_entrant_id") or "")}
    actual = {value for value in snapshot.get("entrant_ids", []) if value}
    return bool(expected - {""}) and actual == expected

def generate_lobby_password() -> str:
    return str(random.randint(1000, 9999))

async def call_match_core(
    set_id: str, *, source: str = "manual", workspace_id: str | None = None,
) -> dict:
    """The single 'Call Match' path shared by the Hub button AND the AI agent.

    Moves the set not_started → called THROUGH the state machine (validated by
    transition_match), then enqueues the standard `call_match` hub command — which
    the bot drains to open the check-in thread. No raw status writes, no ad-hoc
    Discord logic: every caller respects workflows.json and the check-in gate.

    Returns {"ok": True, set_id, p1_name, p2_name} or {"error": "..."}.
    """
    from backend.core.database import get_active_match, add_hub_command, add_bot_feed as _feed
    match = (await get_active_match(set_id, workspace_id)
             if workspace_id is not None else await get_active_match(set_id))
    if not match:
        return {"error": "Match not found"}
    from backend.core.database import get_tournament
    tournament = await get_tournament(match.get("tournament_slug") or "", match.get("workspace_id"))
    if tournament and tournament.get("provider_type") == "challonge" and get_provider_feature_flags().challonge_local_workflow_enabled:
        from backend.core.match_commands import MatchCommandError, MatchCommandService
        try:
            service = (MatchCommandService(workspace_id=workspace_id)
                       if workspace_id is not None else MatchCommandService())
            result = await service.call(set_id)
        except MatchCommandError as exc:
            return {"error": str(exc)}
        local = result["match"]
        return {"ok": True, "set_id": set_id, "p1_name": local.get("p1_name"), "p2_name": local.get("p2_name"), "outcome": "local_only"}
    result = await transition_match(set_id, "called", workspace_id=workspace_id)
    if result.get("error"):
        return result
    await add_hub_command(f"call_match {set_id}", source=source, workspace_id=match.get("workspace_id"))
    await _feed(f"Players called for match: {match.get('p1_name')} vs {match.get('p2_name')}")
    return {
        "ok": True,
        "set_id": set_id,
        "p1_name": match.get("p1_name"),
        "p2_name": match.get("p2_name"),
    }

async def transition_match(
    set_id: str, to_status: str, *, workspace_id: str | None = None,
    skip_provider: bool = False, **kwargs,
) -> dict:
    match = await get_active_match(set_id, workspace_id)
    if not match:
        return {"error": "Match not found"}

    # Challonge has no equivalent lifecycle endpoint.  When Phase 7A is
    # explicitly enabled, route only its local lifecycle through the durable
    # workflow/outbox service. Start.gg (and all flags-off paths) retain the
    # exact legacy transition behavior below.
    from backend.core.database import get_tournament
    tournament = await get_tournament(match.get("tournament_slug") or "", match.get("workspace_id"))
    if tournament and tournament.get("provider_type") == "challonge" and get_provider_feature_flags().challonge_local_workflow_enabled:
        from backend.core.match_commands import MatchCommandError, MatchCommandService
        service = (MatchCommandService(workspace_id=workspace_id)
                   if workspace_id is not None else MatchCommandService())
        try:
            if to_status == "called":
                return {"ok": True, "status": "called", **await service.call(set_id)}
            if to_status == "in_progress":
                return {"ok": True, "status": "in_progress", **await service.start(set_id)}
        except MatchCommandError as exc:
            return {"error": str(exc)}

    current = match.get("status", "not_started")
    if not validate_transition(current, to_status):
        return {"error": f"Cannot transition from {current} to {to_status}"}

    update_kwargs = {
        "status": to_status,
        "hub_status": to_status,
        "hub_status_origin": "local_workflow",
        **kwargs,
    }
    # Only terminal transitions can advance a station queue.  Initialize this
    # for every branch so called -> in_progress never reads an undefined local.
    station_to_advance = None

    if to_status == "called":
        now_dt = datetime.datetime.now(datetime.UTC)
        now = now_dt.isoformat()
        provider_timer = (
            tournament.get("provider_dq_timer_seconds")
            if tournament and tournament.get("provider_type") == "startgg"
            else None
        )
        timeout_seconds = int(provider_timer or (tournament or {}).get("dq_timer_seconds") or 600)
        update_kwargs["called_at"] = now
        update_kwargs["attendance_deadline"] = (
            now_dt + datetime.timedelta(seconds=timeout_seconds)
        ).isoformat()
        update_kwargs["attendance_protected_at"] = None
        update_kwargs["broadcast_state"] = "queued" if match.get("is_stream_match") else "off_air"
        update_kwargs["broadcast_started_at"] = None
        update_kwargs["broadcast_ended_at"] = None
        update_kwargs["p1_ready"] = False
        update_kwargs["p2_ready"] = False
        update_kwargs["p1_attendance_state"] = "pending"
        update_kwargs["p2_attendance_state"] = "pending"
        update_kwargs["p1_attendance_updated_at"] = None
        update_kwargs["p2_attendance_updated_at"] = None
        update_kwargs["p1_attendance_source"] = None
        update_kwargs["p2_attendance_source"] = None

    elif to_status == "in_progress":
        update_kwargs["started_at"] = datetime.datetime.utcnow().isoformat()
        # Push state to start.gg exactly once.  The targeted read is the
        # precondition check at command execution time (not button time), and
        # the second read verifies the provider result before local state moves.
        if not skip_provider:
            try:
                provider = await get_provider_for_tournament(
                    match.get("tournament_slug") or "", match.get("workspace_id")
                )
                preflight = await _startgg_targeted_snapshot(match, provider)
                if preflight is not None:
                    remote_state = preflight.get("state")
                    if not _startgg_precondition_matches(match, preflight):
                        reason = "Start.gg match entrants changed or are unresolved; review required"
                        from backend.core.database import set_match_sync_status_v2
                        await set_match_sync_status_v2(
                            set_id, "needs_review", reason=reason,
                            workspace_id=match.get("workspace_id"),
                        )
                        await add_bot_feed(f"⚠️ {set_id}: {reason}", "warn", workspace_id=match.get("workspace_id"))
                        return {"error": reason, "sync_status": "needs_review"}
                    if remote_state in {ProviderSetState.COMPLETE, ProviderSetState.INVALID}:
                        reason = f"Start.gg match is already terminal ({remote_state.name.lower()}); review required"
                        from backend.core.database import set_match_sync_status_v2
                        await set_match_sync_status_v2(
                            set_id, "needs_review", reason=reason,
                            workspace_id=match.get("workspace_id"),
                        )
                        await add_bot_feed(f"⚠️ {set_id}: {reason}", "warn", workspace_id=match.get("workspace_id"))
                        return {"error": reason, "sync_status": "needs_review"}
                    # A provider already at the intended state is reconciled;
                    # never send a duplicate mutation.
                    if remote_state != ProviderSetState.IN_PROGRESS:
                        mutation_error = None
                        result = None
                        postflight = None
                        try:
                            from backend.core.provider_commands import DurableProviderMutationService
                            result = await DurableProviderMutationService(
                                workspace_id=str(match.get("workspace_id") or "")
                            ).dispatch(
                                match_id=set_id, action="mark_in_progress",
                                payload={"set_id": set_id},
                                operation=lambda: provider.mark_in_progress(set_id),
                                precondition_revision=match.get("provider_revision"),
                            )
                            if not result.success:
                                mutation_error = result.error_message or "Start.gg rejected markSetInProgress"
                        except Exception as exc:
                            # A timeout can happen after the provider applied the
                            # mutation.  Re-read before deciding whether review
                            # is required; never blindly retry here.
                            mutation_error = str(exc)[:300]
                        if mutation_error:
                            postflight = None
                            try:
                                postflight = await _startgg_targeted_snapshot(match, provider)
                            except Exception:
                                postflight = None
                            if postflight and _startgg_precondition_matches(match, postflight) \
                                    and postflight.get("state") == ProviderSetState.IN_PROGRESS:
                                # The remote effect is proven despite an
                                # uncertain response. Continue without resend.
                                remote_state = ProviderSetState.IN_PROGRESS
                            else:
                                reason = mutation_error
                                from backend.core.database import set_match_sync_status_v2
                                await set_match_sync_status_v2(
                                    set_id, "needs_review", reason=reason,
                                    workspace_id=match.get("workspace_id"),
                                )
                                await add_bot_feed(
                                    f"⚠️ markSetInProgress failed for {set_id}: {reason}", "error",
                                    workspace_id=match.get("workspace_id"),
                                )
                                return {
                                    "error": reason, "sync_status": "needs_review",
                                    "provider_diagnostics": getattr(result, "diagnostics", None),
                                }
                        if postflight is None:
                            postflight = await _startgg_targeted_snapshot(match, provider)
                        if postflight is None or postflight.get("state") != ProviderSetState.IN_PROGRESS:
                            reason = "Start.gg activation outcome could not be verified; review required"
                            from backend.core.database import set_match_sync_status_v2
                            await set_match_sync_status_v2(
                                set_id, "needs_review", reason=reason,
                                workspace_id=match.get("workspace_id"),
                            )
                            await add_bot_feed(f"⚠️ {set_id}: {reason}", "error", workspace_id=match.get("workspace_id"))
                            return {"error": reason, "sync_status": "needs_review"}
            except Exception as exc:
                reason = f"Start.gg activation preflight failed: {str(exc)[:300]}"
                from backend.core.database import set_match_sync_status_v2
                await set_match_sync_status_v2(
                    set_id, "needs_review", reason=reason,
                    workspace_id=match.get("workspace_id"),
                )
                await add_bot_feed(f"⚠️ {set_id}: {reason}", "error", workspace_id=match.get("workspace_id"))
                return {"error": reason, "sync_status": "needs_review"}

        # Queue the local score-request effect only after any remote
        # precondition/mutation has succeeded (or an explicit local-only force).
        if match.get("bot_enabled", True):
            from backend.core.database import add_hub_command
            await add_hub_command(f"dm_score_request {set_id}", workspace_id=match.get("workspace_id"))

        # Realize any JSON-defined overlay derived from in_progress (e.g.
        # `on_stream`): bind the stream station at this exact transition point.
        await _realize_in_progress_overlays(match, update_kwargs)
        if match.get("is_stream_match"):
            if update_kwargs.get("broadcast_state"):
                pass
            elif update_kwargs.get("station_id") or match.get("station_id"):
                update_kwargs["broadcast_state"] = "live"
                update_kwargs["broadcast_started_at"] = datetime.datetime.now(datetime.UTC).isoformat()
            else:
                update_kwargs["broadcast_state"] = "ready"
        else:
            update_kwargs["broadcast_state"] = "off_air"

    elif to_status == "complete":
        # The `on_stream` overlay ends with the match — free the station the
        # instant it completes so it's available for the next stream match.
        station_to_advance = match.get("station_id")
        update_kwargs["station_id"] = None
        if match.get("is_stream_match") or match.get("broadcast_state") in {"queued", "ready", "live"}:
            update_kwargs["broadcast_state"] = "ended"
            update_kwargs["broadcast_ended_at"] = datetime.datetime.now(datetime.UTC).isoformat()

    elif to_status == "not_started":
        update_kwargs["p1_score"] = 0
        update_kwargs["p2_score"] = 0
        update_kwargs["p1_ready"] = False
        update_kwargs["p2_ready"] = False
        update_kwargs["called_at"] = None
        update_kwargs["started_at"] = None
        update_kwargs["dq_player"] = None
        update_kwargs["lobby_password"] = None
        update_kwargs["p1_attendance_state"] = "pending"
        update_kwargs["p2_attendance_state"] = "pending"
        update_kwargs["p1_attendance_updated_at"] = None
        update_kwargs["p2_attendance_updated_at"] = None
        update_kwargs["p1_attendance_source"] = None
        update_kwargs["p2_attendance_source"] = None
        update_kwargs["attendance_protected_at"] = None
        update_kwargs["broadcast_state"] = "queued" if match.get("is_stream_match") else "off_air"
        update_kwargs["broadcast_started_at"] = None
        update_kwargs["broadcast_ended_at"] = None
    await upsert_active_match(
        set_id, workspace_id=match.get("workspace_id") or workspace_id, **update_kwargs,
    )

    if station_to_advance:
        try:
            from backend.core.database import advance_station_queue, assign_station_to_active_match
            ws = match.get("workspace_id") or workspace_id
            next_match = await advance_station_queue(station_to_advance, workspace_id=ws)
            if next_match:
                next_set_id = next_match["set_id"]
                await assign_station_to_active_match(
                    next_set_id, station_to_advance, workspace_id=ws
                )
                await transition_match(
                    next_set_id, "in_progress",
                    workspace_id=ws,
                    skip_provider=True
                )
                await hub_mgr.broadcast_to_slot(station_to_advance, {"type": "match_update"}, ws)
        except Exception as queue_err:
            print(f"Error advancing station queue for {station_to_advance}: {queue_err}")

    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": match.get("workspace_id")})
    return {"ok": True, "status": to_status}

async def auto_dq_match(set_id: str, workspace_id: str | None = None) -> dict:
    """Deprecated safety shim: attendance expiry can only request review.

    Start.gg owns native check-in expiry and Challonge permits only an explicit
    organizer-selected forfeit.  Keeping this callable harmless protects old
    workers or queued callbacks during the Phase-11 rollout.
    """
    match = (await get_active_match(set_id, workspace_id)
             if workspace_id is not None else await get_active_match(set_id))
    if not match:
        return {"error": "Match not found"}
    await update_active_match(
        set_id, workspace_id=match.get("workspace_id") or workspace_id,
        sync_status="needs_review",
        sync_reason="Attendance expiry requires provider reconciliation or organizer review; automatic DQ is disabled",
    )
    await add_bot_feed(
        f"⏰ Attendance review requested for {set_id}; automatic DQ is disabled and no provider result was sent.",
        "warn",
        workspace_id=match.get("workspace_id") or workspace_id,
    )
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": match.get("workspace_id")})
    return {"ok": False, "skipped": "automatic_dq_disabled", "needs_review": True}

async def start_call_timer(
    set_id: str, timeout_seconds: int = 600, workspace_id: str | None = None,
):
    await asyncio.sleep(timeout_seconds)
    match = (await get_active_match(set_id, workspace_id)
             if workspace_id is not None else await get_active_match(set_id))
    if not match or match.get("status") != "called":
        return
    # Auto-DQ is deliberately disabled platform-wide.  The timer is retained
    # only as an attendance warning; an organizer must choose the single-player
    # manual DQ through the authorized workflow.  This keeps a timeout from
    # inventing a winner or issuing a provider mutation.
    if match.get("auto_dq_disarmed"):
        message = (
            f"⏰ Call timer expired for {set_id} — automatic DQ is disabled; "
            "an organizer must resolve attendance manually."
        )
        if workspace_id is None and not match.get("workspace_id"):
            await add_bot_feed(message, "info")
        else:
            await add_bot_feed(message, "info", workspace_id=match.get("workspace_id") or workspace_id)
        return
    message = (
        f"⏰ Call timer expired for match {set_id} — automatic DQ is disabled; "
        "review attendance and use manual DQ if appropriate."
    )
    if workspace_id is None and not match.get("workspace_id"):
        await add_bot_feed(message, "warn")
    else:
        await add_bot_feed(message, "warn", workspace_id=match.get("workspace_id") or workspace_id)
