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
        if name == "on_stream" and not match.get("station_id"):
            from backend.core.database import get_available_stream_station
            station = await get_available_stream_station(match.get("event_id") or "", match.get("workspace_id"))
            if station:
                update_kwargs["station_id"] = station["id"]
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
        request, lambda: provider.fetch_snapshot_v2(request)
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

    update_kwargs = {"status": to_status, **kwargs}

    if to_status == "called":
        now = datetime.datetime.utcnow().isoformat()
        update_kwargs["called_at"] = now
        update_kwargs["p1_ready"] = False
        update_kwargs["p2_ready"] = False

    elif to_status == "in_progress":
        update_kwargs["started_at"] = datetime.datetime.utcnow().isoformat()
        # Push state to start.gg exactly once.  The targeted read is the
        # precondition check at command execution time (not button time), and
        # the second read verifies the provider result before local state moves.
        if not skip_provider:
            try:
                provider = await get_provider_for_tournament(
                    match.get("tournament_slug") or "", match.get("workspace_id")
                ) if match.get("workspace_id") is not None else await get_provider_for_tournament(
                    match.get("tournament_slug") or ""
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
                            result = await provider.mark_in_progress(set_id)
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

    elif to_status == "complete":
        # The `on_stream` overlay ends with the match — free the station the
        # instant it completes so it's available for the next stream match.
        update_kwargs["station_id"] = None

    elif to_status == "not_started":
        update_kwargs["p1_score"] = 0
        update_kwargs["p2_score"] = 0
        update_kwargs["p1_ready"] = False
        update_kwargs["p2_ready"] = False
        update_kwargs["called_at"] = None
        update_kwargs["started_at"] = None
        update_kwargs["dq_player"] = None
        update_kwargs["lobby_password"] = None

    await upsert_active_match(
        set_id, workspace_id=match.get("workspace_id") or workspace_id, **update_kwargs,
    )
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": match.get("workspace_id")})
    return {"ok": True, "status": to_status}

async def auto_dq_match(set_id: str, workspace_id: str | None = None) -> dict:
    match = (await get_active_match(set_id, workspace_id)
             if workspace_id is not None else await get_active_match(set_id))
    if not match:
        return {"error": "Match not found"}

    from backend.core.database import get_tournament
    tournament = await get_tournament(match.get("tournament_slug") or "", match.get("workspace_id"))
    if tournament and tournament.get("provider_type") == "challonge":
        # DQ is deliberately unavailable until the later sandbox policy gate.
        return {"ok": False, "skipped": "challonge_dq_unavailable"}

    # Hard guard: if a TO/player flipped the disarm flag (partial-reach matches,
    # off-Discord coordination) we must NOT issue a DQ regardless of who pressed Ready.
    if match.get("auto_dq_disarmed"):
        await add_bot_feed(
            f"auto_dq_match called for {set_id} but match is disarmed — skipping mutation", "warn"
        )
        return {"ok": False, "skipped": "disarmed"}

    provider = await get_provider_for_tournament(match.get("tournament_slug") or "", match.get("workspace_id"))

    # Race guard: if start.gg already shows COMPLETED (players self-reported on the
    # web UI while we were waiting), do NOT call mark_dq — it would overwrite a real
    # result with a DQ flag. Sync local state instead.
    try:
        sgg_state = await provider.fetch_set_state(set_id)
    except Exception:
        sgg_state = None
    # SGG_STATE_MAP: 3 == COMPLETE on start.gg. We import via the enum to stay provider-agnostic.
    from backend.core.contracts.tournament_types import ProviderSetState
    if sgg_state == ProviderSetState.COMPLETE:
        await add_bot_feed(
            f"auto_dq_match skipped for {set_id}: start.gg already shows COMPLETED. Syncing local state instead.",
            "info"
        )
        await update_active_match(
            set_id, workspace_id=match.get("workspace_id") or workspace_id,
            status="complete", dq_player=None, station_id=None,
        )
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": match.get("workspace_id")})
        return {"ok": True, "synced_from_provider": True}

    p1_ready = match.get("p1_ready")
    p2_ready = match.get("p2_ready")
    p1_eid = match.get("p1_entrant_id")
    p2_eid = match.get("p2_entrant_id")

    if not p1_ready and p2_ready:
        dq_eid = p1_eid
        winner_eid = p2_eid
    elif p1_ready and not p2_ready:
        dq_eid = p2_eid
        winner_eid = p1_eid
    else:
        # Double no-show — neither (or, defensively, both) checked in. DQ BOTH.
        dq_eid = "both"
        winner_eid = None

    # Validate the local move BEFORE touching the provider so we never fire a
    # mutation we'd then refuse to record locally (e.g. an already-complete set).
    current = match.get("status", "not_started")
    if not validate_transition(current, "complete"):
        await add_bot_feed(f"auto-DQ blocked: cannot transition {current} → complete for {set_id}", "warn")
        return {"error": True, "message": f"Invalid transition from {current}"}

    if dq_eid == "both":
        # Resolve the set on the provider so the bracket doesn't stall. start.gg
        # can't DQ both slots in one call — it advances one as a technical winner —
        # so warn the TO to verify the advanced slot upstream.
        if p1_eid and p2_eid:
            result = await provider.mark_double_dq(set_id, p1_eid, p2_eid)
            if not result.success:
                await add_bot_feed(f"Provider double-DQ failed for match {set_id}: {result.error_message}", "error")
                return {"error": True, "dq_player": "both", "message": result.error_message}
            await add_bot_feed(
                f"⚠️ Double no-show {set_id}: both players DQ'd. start.gg advanced one slot as a "
                "technical resolution (its API can't DQ both) — verify the next round.", "warn"
            )
    elif winner_eid:
        try:
            result = await provider.mark_dq(set_id, winner_eid)
            if not result.success:
                raise Exception(result.error_message or "Unknown provider error")
        except Exception as e:
            await add_bot_feed(f"Provider auto-DQ failed for match {set_id}: {e}", "error")
            # Do not flip local status if provider rejected — keeps states aligned.
            return {"error": True, "dq_player": dq_eid, "message": str(e)}

    await update_active_match(
        set_id, workspace_id=match.get("workspace_id") or workspace_id,
        status="complete", dq_player=dq_eid, station_id=None,
    )
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": match.get("workspace_id")})
    return {"ok": True, "dq_player": dq_eid}

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
