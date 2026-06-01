from fastapi import APIRouter, Request, HTTPException, Depends, status, Query
import datetime
from typing import Dict, Any, List, Optional
from backend.core.database import (
    get_active_matches, get_active_match, upsert_active_match, delete_active_match,
    get_all_player_overrides, add_bot_feed, add_hub_command, get_match_occupying_station,
    get_station_stream_id,
)
from backend.core.providers.registry import get_provider_for_tournament
from backend.core.score_reporting import report_score_to_provider
from backend.core.match_state import transition_match
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password
from backend.api.schemas import (
    CreateActiveMatchRequest, PatchActiveMatchRequest, PlayerReadyRequest, ToggleStreamRequest,
    DQRequest, ResolveConflictRequest, MessageResponse, ErrorResponse, ActiveMatchesResponse, ConflictsResponse
)

router = APIRouter(tags=["matches"])


async def _sync_provider_stream(set_id: str, station_id: Optional[str], tournament_slug: str) -> None:
    """Best-effort: push the set onto the provider stream queue if the station is mapped.

    Never raises — start.gg streaming is a cosmetic enhancement, not a critical path.
    Failures (missing scope, preview set, unmapped station) are logged to bot_feed only.
    """
    if not station_id:
        return
    stream_id = await get_station_stream_id(station_id)
    if not stream_id:
        return  # Station has no start.gg stream mapping — local-only, no-op.
    try:
        provider = await get_provider_for_tournament(tournament_slug or "")
        result = await provider.assign_stream(set_id, stream_id)
        if not result.success:
            await add_bot_feed(
                f"assignStream skipped for {set_id}: {result.error_message}", "warn"
            )
    except Exception as e:
        await add_bot_feed(f"assignStream error for {set_id}: {e}", "warn")


async def _remove_provider_stream(set_id: str, tournament_slug: str) -> None:
    """Best-effort removal of a set from the provider stream queue."""
    try:
        provider = await get_provider_for_tournament(tournament_slug or "")
        await provider.remove_stream(set_id)
    except Exception as e:
        await add_bot_feed(f"removeStream error for {set_id}: {e}", "warn")


async def auto_assign_free_station(set_id: str):
    from backend.core.database import get_stations, get_active_matches, upsert_active_match
    stations = await get_stations()
    active_matches = await get_active_matches()
    available_stations = [st for st in stations if not st.get("hidden")]
    if not available_stations:
        return None
    used_station_ids = set()
    for am in active_matches:
        if am.get("set_id") != set_id and am.get("status") in ["not_started", "called", "in_progress"] and am.get("station_id"):
            used_station_ids.add(am.get("station_id"))
    for st in available_stations:
        if st["id"] not in used_station_ids:
            await upsert_active_match(set_id, station_id=st["id"])
            # If this station is mapped to a start.gg stream, push the set onto it.
            this_match = await get_active_match(set_id)
            await _sync_provider_stream(set_id, st["id"], (this_match or {}).get("tournament_slug") or "")
            return st["id"]
    return None


@router.get(
    "/active-matches",
    summary="List active matches",
    response_model=ActiveMatchesResponse,
    operation_id="listActiveMatches"
)
async def api_active_matches(
    tournament_slug: Optional[str] = Query(default=None, description="Optional tournament slug to filter the active matches list by")
):
    """Retrieve all active matches that are currently registered for tracking. Supports filtering by tournament slug."""
    matches = await get_active_matches(tournament_slug)
    overrides = await get_all_player_overrides()
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
    return ActiveMatchesResponse(matches=matches)


@router.post(
    "/active-matches",
    dependencies=[Depends(verify_hub_password)],
    summary="Create or upsert an active match",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    operation_id="createActiveMatch"
)
async def api_create_active_match(body: CreateActiveMatchRequest):
    """Register a new active bracket set/match in the local database for tracking. Requires admin password authentication."""
    sid = body.set_id
    if not sid or sid == "None":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="set_id is required")
    await upsert_active_match(sid, **body.model_dump(exclude={"set_id"}))
    await hub_mgr.broadcast({"type": "match_update"})
    return MessageResponse(message="Created", ok=True)


@router.post(
    "/active-matches/{set_id}/activate",
    dependencies=[Depends(verify_hub_password)],
    summary="Activate a match",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="activateMatch"
)
async def api_activate_match(set_id: str):
    """Activate a match by pushing its state live. Calls start.gg markSetInProgress for normal play. Requires admin password authentication."""
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    current_status = m.get("status", "not_started")
    if current_status == "called":
        provider = await get_provider_for_tournament(m.get("tournament_slug") or "")
        provider_result = await provider.mark_in_progress(set_id)
        if not provider_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider activation failed: {provider_result.error_message}"
            )
        await transition_match(set_id, "in_progress")
        return MessageResponse(message="Match activated (in progress)", ok=True)
    else:
        await transition_match(set_id, "not_started")
        return MessageResponse(message="Match activated", ok=True)


@router.post(
    "/active-matches/{set_id}/force-in-progress",
    dependencies=[Depends(verify_hub_password)],
    summary="Force a called match into in-progress (local-safe)",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="forceMatchInProgress"
)
async def api_force_in_progress(set_id: str):
    """Manually elevate a CALLED match to IN_PROGRESS without requiring a provider write.

    Unlike /activate (which hard-fails if start.gg markSetInProgress fails), this routes
    through transition_match() whose provider.mark_in_progress call is best-effort — so it
    works for purely local matches that have no start.gg set. Used by the hub's
    'Force to In-Progress' control for local matches checked in by hand. Requires admin auth.
    """
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if m.get("status") != "called":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a called match can be forced to in-progress."
        )
    result = await transition_match(set_id, "in_progress")
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    await add_bot_feed(f"⏩ Match forced to in-progress: {m.get('p1_name')} vs {m.get('p2_name')}", "info")
    return MessageResponse(message="Forced to in-progress", ok=True)


@router.post(
    "/active-matches/{set_id}/call",
    dependencies=[Depends(verify_hub_password)],
    summary="Call players for a match via Discord",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="callMatch"
)
async def api_call_match(set_id: str):
    """Transition match status to called, trigger bot notification, and start the check-in timer. Requires admin password auth."""
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    result = await transition_match(set_id, "called")
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    
    if m.get("is_stream_match"):
        await auto_assign_free_station(set_id)

    called_at = datetime.datetime.utcnow().isoformat()
    await add_hub_command(f"call_match {set_id}")
    await add_bot_feed(f"Players called for match: {m['p1_name']} vs {m['p2_name']}")
    return MessageResponse(message=f"Players called at {called_at}", ok=True)


@router.post(
    "/active-matches/{set_id}/player-ready",
    summary="Mark a player as ready (no auth - used by Discord bot)",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="setPlayerReady"
)
async def api_player_ready(set_id: str, body: PlayerReadyRequest):
    """Mark a player as checked-in and ready for active combat. Invoked automatically by Discord bot without admin authentication."""
    player = body.player
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    await upsert_active_match(set_id, **{f"{player}_ready": True})
    match = await get_active_match(set_id)
    if match.get("p1_ready") and match.get("p2_ready"):
        await transition_match(set_id, "in_progress")
    return MessageResponse(message="Ready updated", ok=True)


@router.post(
    "/active-matches/{set_id}/toggle-stream",
    dependencies=[Depends(verify_hub_password)],
    summary="Toggle stream match flag",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="toggleStreamMatch"
)
async def api_toggle_stream(set_id: str, body: ToggleStreamRequest):
    """Mark a match as active on stream, assigning a free OBS broadcast station layout if required. Requires admin password auth."""
    m = await get_active_match(set_id)
    if not m:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    await upsert_active_match(set_id, is_stream_match=body.is_stream_match)
    if body.is_stream_match:
        if m.get("status") in ["called", "in_progress"] and not m.get("station_id"):
            await auto_assign_free_station(set_id)
        else:
            # Station already assigned — try to push onto provider stream queue too.
            await _sync_provider_stream(set_id, m.get("station_id"), m.get("tournament_slug") or "")
    else:
        # Toggling off — pull from provider stream queue (best effort).
        await _remove_provider_stream(set_id, m.get("tournament_slug") or "")
    await hub_mgr.broadcast({"type": "match_update"})
    return MessageResponse(message="Stream toggle updated", ok=body.is_stream_match)


@router.post(
    "/active-matches/{set_id}/send",
    dependencies=[Depends(verify_hub_password)],
    summary="Report scores to Start.gg",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="reportSetScore"
)
async def api_send_match(set_id: str):
    """Report match scores directly to Start.gg using validated game data structure. Requires admin password auth."""
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    p1_score = int(m.get('p1_score') or 0)
    p2_score = int(m.get('p2_score') or 0)
    if p1_score == p2_score:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scores cannot be tied.")

    winner_id = m.get('p1_entrant_id') if p1_score > p2_score else m.get('p2_entrant_id')
    if not winner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Winner entrant ID missing.")

    p1_id = str(m.get('p1_entrant_id', ''))
    p2_id = str(m.get('p2_entrant_id', ''))

    provider = await get_provider_for_tournament(m.get('tournament_slug') or '')
    result = await report_score_to_provider(
        set_id=set_id,
        winner_id=winner_id,
        p1_id=p1_id,
        p2_id=p2_id,
        p1_score=p1_score,
        p2_score=p2_score,
        provider=provider
    )
    if result.success:
        await transition_match(set_id, "complete")
        await hub_mgr.broadcast({"type": "match_update"})
        return MessageResponse(message="Score sent successfully.", ok=True)
    else:
        error_msg = result.error_message or "Unknown provider error."
        if "not ready to be reported" in error_msg.lower():
            error_msg = "Bracket not started or set not ready on provider."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provider update error: {error_msg}")


@router.post(
    "/active-matches/{set_id}/reset",
    dependencies=[Depends(verify_hub_password)],
    summary="Reset a completed match",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="resetSet"
)
async def api_reset_match(set_id: str):
    """Reopen a completed bracket set on both Start.gg and FNC Hub local database. Requires admin password auth."""
    m = await get_active_match(set_id)
    tournament_slug = (m or {}).get('tournament_slug') or ''
    try:
        provider = await get_provider_for_tournament(tournament_slug)
        await provider.reset_set(set_id)
    except Exception as e:
        print(f"Provider reset failed: {e}")
    # Also drop from the stream queue — a reset set shouldn't sit in "On Stream".
    await _remove_provider_stream(set_id, tournament_slug)
    await transition_match(set_id, "not_started")
    return MessageResponse(message="Match reset locally and on provider", ok=True)


@router.post(
    "/active-matches/{set_id}/dq",
    dependencies=[Depends(verify_hub_password)],
    summary="Disqualify a player",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="disqualifyPlayer"
)
async def api_dq_match(set_id: str, body: DQRequest):
    """Disqualify an inactive or missing entrant, updating standings correctly on Start.gg. Requires admin password auth."""
    dq_player = body.player
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    dq_eid = None
    try:
        if dq_player != "both":
            winner_eid = m.get('p2_entrant_id') if dq_player == "p1" else m.get('p1_entrant_id')
            dq_eid = m.get('p1_entrant_id') if dq_player == "p1" else m.get('p2_entrant_id')
            if winner_eid:
                provider = await get_provider_for_tournament(m.get('tournament_slug') or '')
                await provider.mark_dq(set_id, winner_eid)
        else:
            dq_eid = "both"
            # Double DQ — resolve the set on the provider too so the bracket doesn't
            # stall. start.gg can only advance one slot (see provider.mark_double_dq).
            p1_eid = m.get('p1_entrant_id')
            p2_eid = m.get('p2_entrant_id')
            if p1_eid and p2_eid:
                provider = await get_provider_for_tournament(m.get('tournament_slug') or '')
                await provider.mark_double_dq(set_id, p1_eid, p2_eid)
    except Exception as e:
        print(f"Provider mark DQ failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider update failed.")
    await transition_match(set_id, "complete", dq_player=dq_eid)
    return MessageResponse(message="DQ marked", ok=True)


@router.delete(
    "/active-matches/{set_id}",
    dependencies=[Depends(verify_hub_password)],
    summary="Remove an active match",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="deleteActiveMatch"
)
async def api_delete_active_match(set_id: str):
    """Delete a match from local active tracking without affecting its state on Start.gg. Requires admin password auth."""
    await delete_active_match(set_id)
    await hub_mgr.broadcast({"type": "match_update"})
    return MessageResponse(message="Deleted", ok=True)


@router.patch(
    "/active-matches/{set_id}",
    dependencies=[Depends(verify_hub_password)],
    summary="Update active match fields",
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    operation_id="patchActiveMatch"
)
async def api_patch_active_match(set_id: str, body: PatchActiveMatchRequest):
    """Safely update active match configurations (scores, station, bot status) using typed parameters. Requires admin password auth."""
    d = body.model_dump(exclude_none=True)
    station_id = d.get("station_id")
    if station_id:
        occupying = await get_match_occupying_station(station_id, exclude_set_id=set_id)
        if occupying:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Station is already occupied by match: {occupying.get('p1_name')} vs {occupying.get('p2_name')}"
            )
    await upsert_active_match(set_id, **d)

    # Assigning a station to a CALLED match elevates it straight to in_progress:
    # transition_match stamps started_at (so the live timer ticks up) and best-effort
    # tells the provider the set is now playing. Routed through the state machine
    # rather than a raw status write so local matches with no start.gg set still work.
    if station_id:
        m = await get_active_match(set_id)
        if m and m.get("status") == "called":
            await transition_match(set_id, "in_progress")

    await hub_mgr.broadcast({"type": "match_update"})
    return MessageResponse(message="Updated", ok=True)


@router.get(
    "/conflicts",
    summary="List score conflicts",
    response_model=ConflictsResponse,
    operation_id="listConflicts"
)
async def api_get_conflicts():
    """Retrieve all match results that have conflicting player score claims. Accessible without authentication."""
    from backend.core.database import get_conflicts, get_active_matches_by_set_ids
    conflicts = await get_conflicts()
    # Enrich each conflict with the live match's player names + entrant IDs so the
    # dashboard can render named "Choose Winner" buttons that post a winner_id.

    set_ids = list({cf.get("set_id") for cf in conflicts if cf.get("set_id")})
    active_matches = await get_active_matches_by_set_ids(set_ids)
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
    dependencies=[Depends(verify_hub_password)],
    summary="Resolve a score conflict",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="resolveConflict"
)
async def api_resolve_conflict(id: int, body: ResolveConflictRequest):
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
        await resolve_conflict(id, body.resolution)
        return MessageResponse(message="Resolved", ok=True)

    if has_scores and body.p1_score == body.p2_score:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resolved score cannot be tied.")

    cf = await get_conflict(id)
    if not cf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict not found")
    set_id = cf.get("set_id")
    m = await get_active_match(set_id) if set_id else None
    if not m:
        # Nothing live to complete — record the decision as a note only.
        await resolve_conflict(id, body.resolution)
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
    await upsert_active_match(set_id, p1_score=p1_score, p2_score=p2_score)

    # Push to the provider. A missing winner entrant means a local-only match —
    # skip the provider call but still complete locally.
    if winner_id:
        provider = await get_provider_for_tournament(m.get("tournament_slug") or "")
        result = await report_score_to_provider(
            set_id=set_id, winner_id=winner_id, p1_id=p1_eid, p2_id=p2_eid,
            p1_score=p1_score, p2_score=p2_score, provider=provider,
        )
        if not result.success:
            error_msg = result.error_message or "Unknown provider error."
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provider update error: {error_msg}")

    await transition_match(set_id, "complete")
    await save_match_result(
        set_id=set_id, tournament_slug=m.get("tournament_slug") or "",
        stream_slot=m.get("station_id") or "",
        p1_name=m.get("p1_name") or "", p2_name=m.get("p2_name") or "",
        winner=str(winner_id), p1_score=str(p1_score), p2_score=str(p2_score),
        round_name=m.get("round_name") or "",
    )
    await resolve_conflict(id, body.resolution or f"TO resolved {p1_score}-{p2_score}")
    await add_bot_feed(
        f"🧑‍⚖️ Conflict resolved by TO (set {set_id}): {p1_score}-{p2_score} reported.", "info"
    )
    await hub_mgr.broadcast({"type": "match_update"})
    return MessageResponse(message="Conflict resolved and reported", ok=True)
