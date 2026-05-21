from fastapi import APIRouter, Request, HTTPException, Depends
import datetime
from backend.core.database import (
    get_active_matches, get_active_match, upsert_active_match, delete_active_match,
    get_all_player_overrides, add_bot_feed, add_hub_command
)
from backend.core.startgg_client import get_client
from backend.core.match_state import transition_match
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password
from backend.api.schemas import (
    CreateActiveMatchRequest, PlayerReadyRequest, ToggleStreamRequest,
    DQRequest, ResolveConflictRequest, MessageResponse, ErrorResponse
)

router = APIRouter(tags=["matches"])
sgg_client = get_client()


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
            return st["id"]
    return None


@router.get("/active-matches", summary="List active matches")
async def api_active_matches(tournament_slug: str = None):
    """Return all active matches, with optional tournament_slug filter."""
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
    return {"matches": matches}


@router.post("/active-matches",
             dependencies=[Depends(verify_hub_password)],
             summary="Create or upsert an active match")
async def api_create_active_match(body: CreateActiveMatchRequest):
    """Register a Start.gg set as an active match for hub tracking."""
    sid = body.set_id
    if not sid or sid == "None":
        raise HTTPException(400, "set_id is required")
    await upsert_active_match(sid, **body.model_dump(exclude={"set_id"}))
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": "Created"}


@router.post("/active-matches/{set_id}/activate",
             dependencies=[Depends(verify_hub_password)],
             summary="Activate a match")
async def api_activate_match(set_id: str):
    """Activate a match (transition called to in_progress, or reset to not_started)."""
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(404)
    
    current_status = m.get("status", "not_started")
    if current_status == "called":
        await transition_match(set_id, "in_progress")
        return {"message": "Match activated (in progress)"}
    else:
        await transition_match(set_id, "not_started")
        return {"message": "Match activated"}


@router.post("/active-matches/{set_id}/call",
             dependencies=[Depends(verify_hub_password)],
             summary="Call players for a match via Discord")
async def api_call_match(set_id: str):
    """Transition match to 'called', send Discord notification, start call timer."""
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(404)
    result = await transition_match(set_id, "called")
    if result.get("error"):
        raise HTTPException(400, result["error"])
    
    if m.get("is_stream_match"):
        await auto_assign_free_station(set_id)

    called_at = datetime.datetime.utcnow().isoformat()
    await add_hub_command(f"call_match {set_id}")
    await add_bot_feed(f"Players called for match: {m['p1_name']} vs {m['p2_name']}")
    return {"message": "Players called", "called_at": called_at}


@router.post("/active-matches/{set_id}/player-ready",
             summary="Mark a player as ready (no auth — used by Discord bot)")
async def api_player_ready(set_id: str, body: PlayerReadyRequest):
    """Mark p1 or p2 as ready. When both ready, auto-transitions to in_progress."""
    player = body.player
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(404)
    await upsert_active_match(set_id, **{f"{player}_ready": True})
    match = await get_active_match(set_id)
    if match.get("p1_ready") and match.get("p2_ready"):
        await transition_match(set_id, "in_progress")
    return {"message": "Ready updated"}


@router.post("/active-matches/{set_id}/toggle-stream",
             dependencies=[Depends(verify_hub_password)],
             summary="Toggle stream match flag")
async def api_toggle_stream(set_id: str, body: ToggleStreamRequest):
    """Mark a match as a stream match for OBS overlay."""
    m = await get_active_match(set_id)
    if m:
        await upsert_active_match(set_id, is_stream_match=body.is_stream_match)
        if body.is_stream_match and m.get("status") in ["called", "in_progress"] and not m.get("station_id"):
            await auto_assign_free_station(set_id)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": "Stream toggle updated", "is_stream_match": body.is_stream_match}


@router.post("/active-matches/{set_id}/send",
             dependencies=[Depends(verify_hub_password)],
             summary="Report scores to Start.gg")
async def api_send_match(set_id: str):
    """Send match scores to Start.gg via gameData. Falls back to winner-only on failure."""
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(404)

    p1_score = int(m.get('p1_score') or 0)
    p2_score = int(m.get('p2_score') or 0)
    if p1_score == p2_score:
        return {"error": True, "message": "Scores cannot be tied."}

    winner_id = m.get('p1_entrant_id') if p1_score > p2_score else m.get('p2_entrant_id')
    if not winner_id:
        return {"error": True, "message": "Winner entrant ID missing."}

    p1_id = str(m.get('p1_entrant_id', ''))
    p2_id = str(m.get('p2_entrant_id', ''))

    try:
        await sgg_client.report_set_score_normal(set_id, winner_id, p1_id, p2_id, p1_score, p2_score)
        await transition_match(set_id, "complete")
        await hub_mgr.broadcast({"type": "match_update"})
        return {"message": "Score sent successfully.", "ok": True}
    except Exception as e1:
        try:
            await sgg_client.report_set_winner_only(set_id, winner_id)
            await transition_match(set_id, "complete")
            await hub_mgr.broadcast({"type": "match_update"})
            return {"message": "Score sent (winner only).", "ok": True}
        except Exception as e2:
            error_msg = str(e2)
            if "not ready to be reported" in error_msg.lower():
                error_msg = "Bracket not started or set not ready on Start.gg."
            return {"error": True, "message": f"Start.gg update error: {error_msg}"}


@router.post("/active-matches/{set_id}/reset",
             dependencies=[Depends(verify_hub_password)],
             summary="Reset a completed match")
async def api_reset_match(set_id: str):
    """Reset match on both Start.gg and local DB to not_started."""
    try:
        await sgg_client.reset_set(set_id)
    except Exception as e:
        print(f"Start.gg reset failed: {e}")
    await transition_match(set_id, "not_started")
    return {"message": "Match reset locally and on Start.gg"}


@router.post("/active-matches/{set_id}/dq",
             dependencies=[Depends(verify_hub_password)],
             summary="Disqualify a player")
async def api_dq_match(set_id: str, body: DQRequest):
    """DQ a player on Start.gg and mark match complete."""
    dq_player = body.player
    m = await get_active_match(set_id)
    if not m:
        raise HTTPException(404)
    dq_eid = None
    try:
        if dq_player != "both":
            winner_eid = m.get('p2_entrant_id') if dq_player == "p1" else m.get('p1_entrant_id')
            dq_eid = m.get('p1_entrant_id') if dq_player == "p1" else m.get('p2_entrant_id')
            if winner_eid:
                await sgg_client.mark_set_dq(set_id, winner_eid)
        else:
            dq_eid = "both"
    except Exception as e:
        print(f"Start.gg mark DQ failed: {e}")
        return {"error": True, "message": "Start.gg update failed."}
    await transition_match(set_id, "complete", dq_player=dq_eid)
    return {"message": "DQ marked"}


@router.delete("/active-matches/{set_id}",
               dependencies=[Depends(verify_hub_password)],
               summary="Remove an active match")
async def api_delete_active_match(set_id: str):
    """Delete match from active tracking without affecting Start.gg."""
    await delete_active_match(set_id)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": "Deleted"}


@router.patch("/active-matches/{set_id}",
              dependencies=[Depends(verify_hub_password)],
              summary="Update active match fields")
async def api_patch_active_match(set_id: str, request: Request):
    """Update arbitrary fields on an active match (scores, swap, station, etc)."""
    d = await request.json()
    station_id = d.get("station_id")
    if station_id:
        active_matches = await get_active_matches()
        for am in active_matches:
            if am.get("set_id") != set_id and am.get("status") in ["not_started", "called", "in_progress"] and am.get("station_id") == station_id:
                raise HTTPException(status_code=400, detail=f"Station is already occupied by match: {am.get('p1_name')} vs {am.get('p2_name')}")
    await upsert_active_match(set_id, **d)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": "Updated"}


@router.get("/conflicts", summary="List score conflicts")
async def api_get_conflicts():
    from backend.core.database import get_conflicts
    return {"conflicts": await get_conflicts()}


@router.post("/conflicts/{id}/resolve",
             dependencies=[Depends(verify_hub_password)],
             summary="Resolve a score conflict")
async def api_resolve_conflict(id: int, body: ResolveConflictRequest):
    from backend.core.database import resolve_conflict
    await resolve_conflict(id, body.resolution)
    return {"message": "Resolved"}
