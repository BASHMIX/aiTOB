from fastapi import APIRouter, Request, HTTPException, Depends, status, Query
import datetime
from typing import Dict, Any, List, Optional
from backend.core.database import (
    get_active_matches, get_active_match, upsert_active_match, delete_active_match,
    get_all_player_overrides, add_bot_feed, add_hub_command, get_match_occupying_station,
    get_station_stream_id, get_station, get_available_stream_station,
    update_station, add_planned_stream, remove_planned_stream, serialize_active_match_for_display,
)
from backend.core.providers.registry import get_provider_for_tournament
from backend.core.score_reporting import report_score_to_provider
from backend.core.match_state import transition_match
from backend.core.match_commands import MatchCommandError, MatchCommandService
from backend.core.provider_feature_flags import get_provider_feature_flags
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import require_permission, optional_session_principal
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import (
    CreateActiveMatchRequest, PatchActiveMatchRequest, PlayerReadyRequest, ToggleStreamRequest,
    DQRequest, ResolveConflictRequest, MessageResponse, ErrorResponse, ActiveMatchesResponse, ConflictsResponse
)

router = APIRouter(tags=["matches"])


def _ws(principal: SessionPrincipal | object) -> str | None:
    # Direct unit calls and the explicitly opt-in legacy bridge operate on
    # historical unowned rows. Real account sessions always carry a workspace.
    if getattr(principal, "legacy", False):
        return None
    return getattr(principal, "workspace_id", None)


async def _local_challonge_enabled(match: dict | None, workspace_id: str | None = None) -> bool:
    """Feature-gated provider ownership check; it performs no provider request."""
    if not match or not get_provider_feature_flags().challonge_local_workflow_enabled:
        return False
    from backend.core.database import get_tournament
    tournament = await get_tournament(match.get("tournament_slug") or "", workspace_id)
    return bool(tournament and tournament.get("provider_type") == "challonge")


async def _challonge_match(match: dict | None, workspace_id: str | None = None) -> bool:
    if not match:
        return False
    from backend.core.database import get_tournament
    tournament = await get_tournament(match.get("tournament_slug") or "", workspace_id)
    return bool(tournament and tournament.get("provider_type") == "challonge")


def _action_projection(match: dict) -> dict | None:
    """Authoritative, non-secret controls for the Phase-7A Challonge card."""
    if match.get("provider_type") != "challonge":
        return None
    flags = get_provider_feature_flags()
    eligibility = match.get("eligibility") or {}
    state_axes = match.get("state_axes") or {}
    eligible = bool(eligibility.get("actionable"))
    local_enabled = flags.challonge_local_workflow_enabled
    hub = state_axes.get("hub_status") or match.get("status")
    # Older tracked rows can retain the pre-V2 ``status`` after being put on a
    # station, while the additive hub_status column is still ``not_started``.
    # Treat the established legacy workflow as authoritative for the action
    # projection until reconciliation updates the hub axis.  This restores the
    # result controls for an actively streamed match without changing any row.
    legacy_status = match.get("status")
    if hub in {"not_started", "available"} and legacy_status in {"called", "ready", "in_progress"}:
        hub = legacy_status
    return {
        "call": {"kind": "local", "enabled": local_enabled and eligible and hub in {"not_started", "available"}, "label": "Call in aiTOB"},
        "ready": {"kind": "local", "enabled": local_enabled and hub in {"called", "ready"}, "label": "Ready in aiTOB"},
        "start": {"kind": "local", "enabled": local_enabled and hub in {"called", "ready"}, "label": "Start locally"},
        "station": {"kind": "local", "enabled": local_enabled, "label": "Assign local station"},
        "report_score": (
            {"kind": "remote", "enabled": local_enabled and eligible and hub in {"called", "ready", "in_progress"}, "label": "Submit result for verification"}
            if flags.challonge_score_commands_enabled
            else {"kind": "unavailable", "enabled": False, "reason": "Challonge score reporting is disabled until provider verification is enabled."}
        ),
        "dq": (
            {"kind": "remote", "enabled": local_enabled and eligible and hub in {"not_started", "available", "called", "ready", "in_progress"}, "label": "Submit DQ (0/-1)"}
            if flags.challonge_dq_commands_enabled
            else {"kind": "unavailable", "enabled": False, "reason": "Challonge manual DQ is disabled. When enabled, its public bracket will show 0/-1 rather than a DQ label."}
        ),
        "reset": {"kind": "unavailable", "enabled": False, "reason": "Challonge reset/reopen is not supported."},
    }


async def _sync_provider_stream(set_id: str, station_id: Optional[str], tournament_slug: str, workspace_id: str | None = None) -> None:
    """Best-effort: push the set onto the provider stream queue if the station is mapped.

    Never raises — start.gg streaming is a cosmetic enhancement, not a critical path.
    Failures (missing scope, preview set, unmapped station) are logged to bot_feed only.
    """
    if not station_id:
        return
    stream_id = await get_station_stream_id(station_id, workspace_id)
    if not stream_id:
        return  # Station has no start.gg stream mapping — local-only, no-op.
    try:
        provider = await get_provider_for_tournament(tournament_slug or "", workspace_id)
        result = await provider.assign_stream(set_id, stream_id)
        if not result.success:
            await add_bot_feed(
                f"assignStream skipped for {set_id}: {result.error_message}", "warn"
            )
    except Exception as e:
        await add_bot_feed(f"assignStream error for {set_id}: {e}", "warn")


async def _remove_provider_stream(set_id: str, tournament_slug: str, workspace_id: str | None = None) -> None:
    """Best-effort removal of a set from the provider stream queue."""
    try:
        provider = await get_provider_for_tournament(tournament_slug or "", workspace_id)
        await provider.remove_stream(set_id)
    except Exception as e:
        await add_bot_feed(f"removeStream error for {set_id}: {e}", "warn")


@router.get(
    "/active-matches",
    summary="List active matches",
    response_model=ActiveMatchesResponse,
    operation_id="listActiveMatches"
)
async def api_active_matches(
    tournament_slug: Optional[str] = Query(default=None, description="Optional tournament slug to filter the active matches list by"),
    event_id: Optional[str] = Query(default=None, description="Optional event ID to scope matches to a single game/bracket (prevents cross-event contamination)"),
    principal: SessionPrincipal | None = Depends(optional_session_principal),
):
    """Retrieve all active matches that are currently registered for tracking. Supports filtering by tournament slug and event."""
    # Anonymous legacy consumers receive an intentionally empty projection;
    # tenant data is never exposed without a trusted session.
    matches = await get_active_matches(tournament_slug, event_id, _ws(principal)) if principal else []
    overrides = await get_all_player_overrides(_ws(principal)) if principal else {}
    for m in matches:
        p1_eid = m.get("p1_entrant_id")
        p2_eid = m.get("p2_entrant_id")
        if p1_eid and p1_eid in overrides:
            ov = overrides[p1_eid]
            if ov.get("name"): m["p1_name"] = ov["name"]
            if ov.get("avatar_url"): m["p1_avatar"] = ov["avatar_url"]
        if p2_eid and p2_eid in overrides:
            ov = overrides[p2_eid]
            if ov.get("name"): m["p2_name"] = ov["name"]
            if ov.get("avatar_url"): m["p2_avatar"] = ov["avatar_url"]
        # Pure serialization: no provider request and no workflow effect.
        m.update(serialize_active_match_for_display(m))
        m["actions"] = _action_projection(m)
    return ActiveMatchesResponse(matches=matches)


@router.post(
    "/active-matches",
    summary="Create or upsert an active match",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    operation_id="createActiveMatch"
)
async def api_create_active_match(body: CreateActiveMatchRequest, principal: SessionPrincipal = Depends(require_permission("match.operate"))):
    """Register a new active bracket set/match in the local database for tracking. Requires admin password authentication."""
    sid = body.set_id
    if not sid or sid == "None":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="set_id is required")
    values = body.model_dump(exclude={"set_id"})
    from backend.core.database import get_tournament
    if not await get_tournament(values.get("tournament_slug") or "", _ws(principal)):
        raise HTTPException(status_code=404, detail="Tournament not found")
    await upsert_active_match(sid, workspace_id=_ws(principal), **values)
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
    return MessageResponse(message="Created", ok=True)


@router.post(
    "/active-matches/{set_id}/activate",
    dependencies=[Depends(require_permission("match.start"))],
    summary="Activate a match",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="activateMatch"
)
async def api_activate_match(set_id: str, principal: SessionPrincipal = Depends(require_permission("match.start"))):
    """Activate a match by pushing its state live. Calls start.gg markSetInProgress for normal play. Requires admin password authentication."""
    m = await get_active_match(set_id, _ws(principal))
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    if await _local_challonge_enabled(m, _ws(principal)):
        try:
            await MatchCommandService(workspace_id=_ws(principal)).start(set_id)
        except MatchCommandError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
        return MessageResponse(message="Match started locally; Challonge remains unchanged.", ok=True)

    current_status = m.get("status", "not_started")
    if current_status == "called":
        result = await transition_match(set_id, "in_progress", workspace_id=_ws(principal))
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"],
            )
        return MessageResponse(message="Match activated (in progress)", ok=True)
    else:
        await transition_match(set_id, "not_started", workspace_id=_ws(principal))
        return MessageResponse(message="Match activated", ok=True)


@router.post(
    "/active-matches/{set_id}/force-in-progress",
    dependencies=[Depends(require_permission("match.start"))],
    summary="Force a called match into in-progress (local-safe)",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="forceMatchInProgress"
)
async def api_force_in_progress(set_id: str, principal: SessionPrincipal = Depends(require_permission("match.start"))):
    """Manually elevate a CALLED match to IN_PROGRESS without requiring a provider write.

    Unlike /activate (which hard-fails if start.gg markSetInProgress fails), this routes
    through transition_match() whose provider.mark_in_progress call is best-effort — so it
    works for purely local matches that have no start.gg set. Used by the hub's
    'Force to In-Progress' control for local matches checked in by hand. Requires admin auth.
    """
    m = await get_active_match(set_id, _ws(principal))
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if m.get("status") != "called":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a called match can be forced to in-progress."
        )
    # This explicit local-safe control intentionally skips a remote provider
    # mutation; /activate owns the Start.gg preflight/mutation/verification path.
    result = await transition_match(set_id, "in_progress", workspace_id=_ws(principal), skip_provider=True)
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    await add_bot_feed(f"⏩ Match forced to in-progress: {m.get('p1_name')} vs {m.get('p2_name')}", "info")
    return MessageResponse(message="Forced to in-progress", ok=True)


@router.post(
    "/active-matches/{set_id}/call",
    dependencies=[Depends(require_permission("match.call"))],
    summary="Call players for a match via Discord",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="callMatch"
)
async def api_call_match(set_id: str, principal: SessionPrincipal = Depends(require_permission("match.call"))):
    """Transition match status to called, trigger bot notification, and start the check-in timer. Requires admin password auth.

    Routes through the shared call_match_core so the Hub button and the AI agent
    take the exact same path: not_started → called (state machine) + enqueue the
    standard `call_match` hub command. No station is bound here — for a stream
    match that's the `on_stream` overlay, bound at the called → in_progress
    transition once both players check in.
    """
    m = await get_active_match(set_id, _ws(principal))
    if await _local_challonge_enabled(m, _ws(principal)):
        try:
            await MatchCommandService(workspace_id=_ws(principal)).call(set_id)
        except MatchCommandError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
        return MessageResponse(message="Players called locally; Discord delivery is queued.", ok=True)
    from backend.core.match_state import call_match_core
    result = await call_match_core(set_id, workspace_id=_ws(principal))
    if result.get("error"):
        code = status.HTTP_404_NOT_FOUND if result["error"] == "Match not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=result["error"])
    return MessageResponse(message="Players called", ok=True)


@router.post(
    "/active-matches/{set_id}/player-ready",
    dependencies=[Depends(require_permission("match.ready"))],
    summary="Mark a player as ready (no auth - used by Discord bot)",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="setPlayerReady"
)
async def api_player_ready(set_id: str, body: PlayerReadyRequest, principal: SessionPrincipal = Depends(require_permission("match.ready"))):
    """Mark a player as checked-in and ready for active combat. Invoked automatically by Discord bot without admin authentication."""
    player = body.player
    m = await get_active_match(set_id, _ws(principal))
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if await _local_challonge_enabled(m, _ws(principal)):
        try:
            await MatchCommandService(workspace_id=_ws(principal)).mark_ready(set_id, body.player)
        except MatchCommandError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
        return MessageResponse(message="Ready recorded locally.", ok=True)
    await upsert_active_match(set_id, workspace_id=_ws(principal), **{f"{player}_ready": True})
    match = await get_active_match(set_id, _ws(principal))
    if match.get("p1_ready") and match.get("p2_ready"):
        await transition_match(set_id, "in_progress", workspace_id=_ws(principal))
    return MessageResponse(message="Ready updated", ok=True)


@router.post(
    "/active-matches/{set_id}/toggle-stream",
    dependencies=[Depends(require_permission("match.stream"))],
    summary="Toggle stream match flag",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="toggleStreamMatch"
)
async def api_toggle_stream(set_id: str, body: ToggleStreamRequest, principal: SessionPrincipal = Depends(require_permission("match.stream"))):
    """Mark a match as active on stream, assigning a free OBS broadcast station layout if required. Requires admin password auth."""
    m = await get_active_match(set_id, _ws(principal))
    if not m:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    tournament_slug = m.get("tournament_slug") or ""
    await upsert_active_match(set_id, workspace_id=_ws(principal), is_stream_match=body.is_stream_match)
    if body.is_stream_match:
        # Station binding is the `on_stream` overlay, realized at the
        # called → in_progress transition (match_state.transition_match). So:
        #   • not_started / called → just set the flag; the match stays in the
        #     normal flow and binds a station when it reaches in_progress.
        #   • already in_progress → the transition already passed, so realize the
        #     overlay NOW: bind a free Event-matching stream station if unbound.
        if m.get("station_id"):
            # Station already assigned — push onto the provider stream queue too.
            await _sync_provider_stream(set_id, m.get("station_id"), tournament_slug, _ws(principal))
        elif m.get("status") == "in_progress":
            station = await get_available_stream_station(m.get("event_id") or "", _ws(principal))
            if station:
                await upsert_active_match(set_id, workspace_id=_ws(principal), station_id=station["id"])
                await _sync_provider_stream(set_id, station["id"], tournament_slug, _ws(principal))
            else:
                await add_bot_feed(
                    f"📺 Match {set_id} flagged for stream but no free stream station "
                    f"for its event — TO to place it via the manual override.", "info"
                )
    else:
        # Rule C: flag OFF ⟹ strictly un-stream it — pull from the provider queue,
        # drop the planned-stream wishlist entry, and unassign the station so it
        # can never be left orphaned on a station it's no longer destined for.
        await _remove_provider_stream(set_id, tournament_slug, _ws(principal))
        await remove_planned_stream(set_id)
        if m.get("station_id"):
            await upsert_active_match(set_id, workspace_id=_ws(principal), station_id=None)
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
    return MessageResponse(message="Stream toggle updated", ok=body.is_stream_match)


@router.post(
    "/active-matches/{set_id}/send",
    dependencies=[Depends(require_permission("result.report"))],
    summary="Report scores to Start.gg",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="reportSetScore"
)
async def api_send_match(set_id: str, principal: SessionPrincipal = Depends(require_permission("result.report"))):
    """Report match scores directly to Start.gg using validated game data structure. Requires admin password auth."""
    m = await get_active_match(set_id, _ws(principal))
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    p1_score = int(m.get('p1_score') or 0)
    p2_score = int(m.get('p2_score') or 0)
    if await _challonge_match(m, _ws(principal)):
        if not get_provider_feature_flags().challonge_score_commands_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Challonge score reporting is disabled until the verified score-command phase.",
            )
        try:
            outcome = await MatchCommandService(workspace_id=_ws(principal)).submit_score(
                set_id, p1_score=p1_score, p2_score=p2_score
            )
        except MatchCommandError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
        if outcome["outcome"] == "verified":
            return MessageResponse(message="Score verified by Challonge.", ok=True)
        return MessageResponse(message="Result submitted — awaiting provider verification.", ok=True)

    if p1_score == p2_score:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scores cannot be tied.")

    winner_id = m.get('p1_entrant_id') if p1_score > p2_score else m.get('p2_entrant_id')
    if not winner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Winner entrant ID missing.")

    p1_id = str(m.get('p1_entrant_id', ''))
    p2_id = str(m.get('p2_entrant_id', ''))

    provider = await get_provider_for_tournament(m.get('tournament_slug') or '', _ws(principal))
    report_kwargs = {
        "set_id": set_id,
        "winner_id": winner_id,
        "p1_id": p1_id,
        "p2_id": p2_id,
        "p1_score": p1_score,
        "p2_score": p2_score,
        "provider": provider,
    }
    if _ws(principal) is not None:
        report_kwargs["workspace_id"] = _ws(principal)
    result = await report_score_to_provider(**report_kwargs)
    if result.success:
        if _ws(principal) is None:
            # Preserve direct unit/legacy callers that have no session
            # principal; authenticated HTTP requests always carry a scope.
            await transition_match(set_id, "complete")
        else:
            await transition_match(set_id, "complete", workspace_id=_ws(principal))
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
        return MessageResponse(message="Score sent successfully.", ok=True)
    else:
        error_msg = result.error_message or "Unknown provider error."
        if "not ready to be reported" in error_msg.lower():
            error_msg = "Bracket not started or set not ready on provider."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provider update error: {error_msg}")


@router.post(
    "/active-matches/{set_id}/reset",
    dependencies=[Depends(require_permission("match.operate"))],
    summary="Reset a completed match",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="resetSet"
)
async def api_reset_match(set_id: str, principal: SessionPrincipal = Depends(require_permission("match.operate"))):
    """Reopen a completed bracket set on both Start.gg and FNC Hub local database. Requires admin password auth."""
    m = await get_active_match(set_id, _ws(principal))
    if await _challonge_match(m, _ws(principal)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Challonge reset/reopen is unavailable.")
    tournament_slug = (m or {}).get('tournament_slug') or ''
    try:
        provider = await get_provider_for_tournament(tournament_slug, _ws(principal))
        await provider.reset_set(set_id)
    except Exception as e:
        print(f"Provider reset failed: {e}")
    # Also drop from the stream queue — a reset set shouldn't sit in "On Stream".
    await _remove_provider_stream(set_id, tournament_slug, _ws(principal))
    await transition_match(set_id, "not_started", workspace_id=_ws(principal))
    return MessageResponse(message="Match reset locally and on provider", ok=True)


@router.post(
    "/active-matches/{set_id}/dq",
    dependencies=[Depends(require_permission("dq.manual"))],
    summary="Disqualify a player",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="disqualifyPlayer"
)
async def api_dq_match(set_id: str, body: DQRequest, principal: SessionPrincipal = Depends(require_permission("dq.manual"))):
    """Disqualify an inactive or missing entrant, updating standings correctly on Start.gg. Requires admin password auth."""
    dq_player = body.player
    m = await get_active_match(set_id, _ws(principal))
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if await _challonge_match(m, _ws(principal)):
        if dq_player == "both":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Both players cannot be DQ'd in Challonge: the bracket needs an organizer-selected winner. No result was sent.",
            )
        if not get_provider_feature_flags().challonge_dq_commands_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Challonge manual DQ is disabled. Enable it only if you accept that the public bracket displays 0/-1, not a DQ label.",
            )
        try:
            outcome = await MatchCommandService(workspace_id=_ws(principal)).submit_forfeit(set_id, dq_player=dq_player)
        except MatchCommandError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
        if outcome["outcome"] == "verified":
            return MessageResponse(message="DQ result verified by Challonge as 0/-1.", ok=True)
        return MessageResponse(message="DQ result submitted as 0/-1 — awaiting provider verification.", ok=True)
    dq_eid = None
    try:
        if dq_player != "both":
            winner_eid = m.get('p2_entrant_id') if dq_player == "p1" else m.get('p1_entrant_id')
            dq_eid = m.get('p1_entrant_id') if dq_player == "p1" else m.get('p2_entrant_id')
            if winner_eid:
                provider = await get_provider_for_tournament(m.get('tournament_slug') or '', _ws(principal))
                await provider.mark_dq(set_id, winner_eid)
        else:
            dq_eid = "both"
            # Double DQ — resolve the set on the provider too so the bracket doesn't
            # stall. start.gg can only advance one slot (see provider.mark_double_dq).
            p1_eid = m.get('p1_entrant_id')
            p2_eid = m.get('p2_entrant_id')
            if p1_eid and p2_eid:
                provider = await get_provider_for_tournament(m.get('tournament_slug') or '', _ws(principal))
                await provider.mark_double_dq(set_id, p1_eid, p2_eid)
    except Exception as e:
        print(f"Provider mark DQ failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider update failed.")
    await transition_match(set_id, "complete", workspace_id=_ws(principal), dq_player=dq_eid)
    return MessageResponse(message="DQ marked", ok=True)


@router.delete(
    "/active-matches/{set_id}",
    dependencies=[Depends(require_permission("match.operate"))],
    summary="Remove an active match",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="deleteActiveMatch"
)
async def api_delete_active_match(set_id: str, principal: SessionPrincipal = Depends(require_permission("match.operate"))):
    """Delete a match from local active tracking without affecting its state on Start.gg. Requires admin password auth."""
    await delete_active_match(set_id, workspace_id=_ws(principal))
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
    return MessageResponse(message="Deleted", ok=True)


@router.patch(
    "/active-matches/{set_id}",
    dependencies=[Depends(require_permission("match.operate"))],
    summary="Update active match fields",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    operation_id="patchActiveMatch"
)
async def api_patch_active_match(set_id: str, body: PatchActiveMatchRequest, principal: SessionPrincipal = Depends(require_permission("match.operate"))):
    """Safely update active match configurations (scores, station, bot status) using typed parameters. Requires admin password auth."""
    # exclude_unset (not exclude_none) so an explicit `station_id: null` from the
    # "Unassign" dropdown is preserved and actually clears the station. Fields the
    # client didn't send are still omitted.
    d = body.model_dump(exclude_unset=True)
    existing_match = await get_active_match(set_id, _ws(principal))
    if "station_id" in d and d.get("station_id") and await _local_challonge_enabled(existing_match, _ws(principal)):
        try:
            await MatchCommandService(workspace_id=_ws(principal)).assign_station(set_id, d["station_id"])
        except MatchCommandError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
        return MessageResponse(message="Station assigned locally; Challonge remains unchanged.", ok=True)
    station_provided = "station_id" in d
    station_id = d.get("station_id")  # may be None when explicitly cleared
    if station_provided and station_id is None and existing_match and existing_match.get("station_id"):
        # A station's physical ownership is separate from the match's display
        # field.  Release it only when this exact match owns it, so clearing a
        # stale row can never evict another tournament's active match.
        previous_station = await get_station(existing_match["station_id"], _ws(principal))
        if previous_station and previous_station.get("active_match_id") == set_id:
            await update_station(existing_match["station_id"], workspace_id=_ws(principal), active_match_id=None)
    if station_id:
        occupying = await get_match_occupying_station(station_id, exclude_set_id=set_id, workspace_id=_ws(principal))
        if occupying:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Station is already occupied by match: {occupying.get('p1_name')} vs {occupying.get('p2_name')}"
            )
    await upsert_active_match(set_id, workspace_id=_ws(principal), **d)

    # ── Strict stream-flag ↔ station coupling (only when station was touched) ──
    if station_provided:
        m = await get_active_match(set_id, _ws(principal))
        slug = (m or {}).get("tournament_slug") or ""

        if station_id:
            # Assigning a station to a CALLED match elevates it straight to
            # in_progress: transition_match stamps started_at (so the live timer
            # ticks up) and best-effort tells the provider the set is now playing.
            # Routed through the state machine rather than a raw status write so
            # local matches with no start.gg set still work.
            if m and m.get("status") == "called":
                await transition_match(set_id, "in_progress", workspace_id=_ws(principal))
                m = await get_active_match(set_id, _ws(principal))

            station = await get_station(station_id, _ws(principal))
            if station and station.get("is_stream_station"):
                # Rule B: a stream station ⟹ this IS a stream match. Flag it on,
                # mirror it onto the planned-stream wishlist (keeps the Hub's Play
                # button coupled + toggle-off-able), and push to the provider queue.
                if not (m or {}).get("is_stream_match"):
                    await upsert_active_match(set_id, workspace_id=_ws(principal), is_stream_match=True)
                    await add_planned_stream(set_id, slug)
                await _sync_provider_stream(set_id, station_id, slug, _ws(principal))
            else:
                # Decision 1: forcing a stream match onto a *non-stream* setup means
                # the TO is pushing it off-stream to save time — strictly un-flag it
                # and pull it from the provider queue / wishlist.
                if (m or {}).get("is_stream_match"):
                    await upsert_active_match(set_id, workspace_id=_ws(principal), is_stream_match=False)
                    await remove_planned_stream(set_id)
                    await _remove_provider_stream(set_id, slug, _ws(principal))
        # else: station explicitly cleared (Unassign). Decision 2: keep the stream
        # flag ON so the dispatcher can re-route the match to another stream station.

    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
    return MessageResponse(message="Updated", ok=True)


@router.get(
    "/conflicts",
    summary="List score conflicts",
    response_model=ConflictsResponse,
    operation_id="listConflicts"
)
async def api_get_conflicts(principal: SessionPrincipal | None = Depends(optional_session_principal)):
    """Retrieve all match results that have conflicting player score claims. Accessible without authentication."""
    from backend.core.database import get_conflicts, get_active_matches_by_set_ids
    conflicts = await get_conflicts(workspace_id=_ws(principal)) if principal else []
    # Enrich each conflict with the live match's player names + entrant IDs so the
    # dashboard can render named "Choose Winner" buttons that post a winner_id.
    set_ids = list({cf.get("set_id") for cf in conflicts if cf.get("set_id")})
    active_matches = await get_active_matches_by_set_ids(set_ids, workspace_id=_ws(principal))
    matches_by_set_id = {m["set_id"]: m for m in active_matches}

    for cf in conflicts:
        set_id = cf.get("set_id")
        m = matches_by_set_id.get(set_id) if set_id else None
        if m:
            cf["p1_name"] = m.get("p1_name")
            cf["p2_name"] = m.get("p2_name")
            cf["p1_entrant_id"] = m.get("p1_entrant_id")
            cf["p2_entrant_id"] = m.get("p2_entrant_id")
    return ConflictsResponse(conflicts=conflicts)


@router.post(
    "/conflicts/{id}/resolve",
    dependencies=[Depends(require_permission("conflict.manage"))],
    summary="Resolve a score conflict",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="resolveConflict"
)
async def api_resolve_conflict(id: int, body: ResolveConflictRequest, principal: SessionPrincipal = Depends(require_permission("conflict.manage"))):
    """Resolve a score conflict.

    If the TO supplies a final score (p1_score + p2_score), the set is completed
    with that score AND reported to the provider — the bracket actually moves on.
    Without a score, the conflict is annotation-only (legacy accept/dismiss).
    Requires admin password auth.
    """
    from backend.core.database import (
        resolve_conflict, get_conflict, save_match_result,
    )

    has_scores = body.p1_score is not None and body.p2_score is not None
    has_winner = bool(body.winner_id)

    # Annotation-only path (no TO decision supplied) — keep legacy behavior.
    if not has_scores and not has_winner:
        await resolve_conflict(id, body.resolution, workspace_id=_ws(principal))
        return MessageResponse(message="Resolved", ok=True)

    if has_scores and body.p1_score == body.p2_score:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resolved score cannot be tied.")

    cf = await get_conflict(id, workspace_id=_ws(principal))
    if not cf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict not found")
    set_id = cf.get("set_id")
    m = await get_active_match(set_id, _ws(principal)) if set_id else None
    if not m:
        # Nothing live to complete — record the decision as a note only.
        await resolve_conflict(id, body.resolution, workspace_id=_ws(principal))
        return MessageResponse(message="Resolved (note only — no active match found)", ok=True)

    p1_eid = str(m.get("p1_entrant_id") or "")
    p2_eid = str(m.get("p2_entrant_id") or "")

    if has_scores:
        p1_score, p2_score = body.p1_score, body.p2_score
        winner_id = p1_eid if p1_score > p2_score else p2_eid
    else:
        # Winner-button flow: TO picked a winner → assign a default 2-0 to them.
        winner_id = str(body.winner_id)
        if winner_id == p1_eid:
            p1_score, p2_score = 2, 0
        elif winner_id == p2_eid:
            p1_score, p2_score = 0, 2
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="winner_id does not match either entrant in this match."
            )

    # Persist the decided score locally first so the overlay/records reflect it.
    await upsert_active_match(set_id, workspace_id=_ws(principal), p1_score=p1_score, p2_score=p2_score)

    # Push to the provider. A missing winner entrant means a local-only match —
    # skip the provider call but still complete locally.
    if winner_id:
        provider = await get_provider_for_tournament(m.get("tournament_slug") or "", _ws(principal))
        result = await report_score_to_provider(
            set_id=set_id, winner_id=winner_id, p1_id=p1_eid, p2_id=p2_eid,
            p1_score=p1_score, p2_score=p2_score, provider=provider,
            workspace_id=_ws(principal),
        )
        if not result.success:
            error_msg = result.error_message or "Unknown provider error."
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provider update error: {error_msg}")

    await transition_match(set_id, "complete", workspace_id=_ws(principal))
    await save_match_result(
        set_id=set_id, tournament_slug=m.get("tournament_slug") or "",
        stream_slot=m.get("station_id") or "",
        p1_name=m.get("p1_name") or "", p2_name=m.get("p2_name") or "",
        winner=str(winner_id), p1_score=str(p1_score), p2_score=str(p2_score),
        round_name=m.get("round_name") or "",
    )
    await resolve_conflict(
        id,
        body.resolution or f"TO resolved {p1_score}-{p2_score}",
        workspace_id=_ws(principal),
    )
    await add_bot_feed(
        f"🧑‍⚖️ Conflict resolved by TO (set {set_id}): {p1_score}-{p2_score} reported.", "info"
    )
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _ws(principal)})
    return MessageResponse(message="Conflict resolved and reported", ok=True)
