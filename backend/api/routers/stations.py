import asyncio
from typing import Any, Mapping

from fastapi import APIRouter, Body, Depends, HTTPException
from collections import defaultdict
from backend.core.database import (
    get_stations, create_station, update_station, delete_station,
    add_station_overlay, remove_station_overlay, get_station_overlays,
    get_all_station_overlays, update_station_active_overlay, get_station,
    get_station_queue, enqueue_station_match, reorder_station_queue, dequeue_station_match
)
from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal, enforce_auth_rate_limit
from backend.core.entitlements import EntitlementLimitExceeded, require_workspace_capacity
from backend.api.schemas import (
    CreateStationRequest, UpdateStationRequest, AddStationOverlayRequest, SetActiveOverlayRequest,
    IssueOverlayAccessRequest,
    BroadcastPreviewRequest,
    EnqueueMatchRequest, ReorderQueueRequest,
)
from datetime import datetime, timezone
from backend.api.results_media_schemas import (
    BindSessionRequest,
    ResultsSessionResponse,
    SessionCommandRequest,
)
from backend.core.database import record_audit_event
from backend.core import results_media
from backend.core.results_media_repository import (
    bind_station_session,
    get_media_output,
    get_result_version_by_id,
    get_station_session,
    get_version_entries,
    update_station_session_command,
)

router = APIRouter(tags=["stations"])

_results_play_all_tasks: set[asyncio.Task[None]] = set()


def _results_sequence_timing(scene: Mapping[str, Any] | None) -> tuple[int, int]:
    """Return persisted start/stagger timing for the first live results consumer."""
    nodes = scene.get("nodes") if isinstance(scene, Mapping) else None
    if isinstance(nodes, Mapping):
        for node in nodes.values():
            if not isinstance(node, Mapping):
                continue
            if node.get("type") != "results-group" or node.get("mode") != "sequence":
                if node.get("type") == "results-cards":
                    auto_sequence = node.get("autoSequence")
                    if isinstance(auto_sequence, Mapping) and auto_sequence.get("enabled") is True:
                        return 0, int(auto_sequence.get("delayBetweenStartsMs", 500))
                    schedule = node.get("schedule")
                    if isinstance(schedule, Mapping):
                        interval = int(schedule.get("delayBetweenStartsMs", 500))
                        if schedule.get("trigger") == "after-previous":
                            child_ids = node.get("childIds")
                            first_child = nodes.get(child_ids[0]) if isinstance(child_ids, list) and child_ids else None
                            lifecycle = first_child.get("outerAnimation") if isinstance(first_child, Mapping) else None
                            if isinstance(lifecycle, Mapping):
                                interval += sum(
                                    int(lifecycle.get(key, 0))
                                    for key in ("enterDurationMs", "visibleHoldMs", "exitDurationMs")
                                )
                        return 0, interval
                continue
            sequence = node.get("sequence")
            if isinstance(sequence, Mapping):
                return int(sequence.get("startDelayMs", 300)), int(sequence.get("intervalMs", 800))
    return 300, 800


async def _broadcast_results_session(
    workspace_id: str,
    station_id: str,
    session: Mapping[str, Any],
) -> None:
    from backend.api.ws_manager import manager as ws_manager

    event = {
        "type": "results_session_update",
        "station_id": station_id,
        "session": {
            "media_output_id": session.get("media_output_id"),
            "state": session.get("state"),
            "cue_index": session.get("cue_index"),
            "session_revision": session.get("session_revision"),
            "updated_at": session.get("updated_at"),
        },
    }
    await ws_manager.broadcast_to_slot(station_id, event, workspace_id)
    await ws_manager.broadcast({**event, "_workspace_id": workspace_id})


async def _run_results_play_all(
    *,
    workspace_id: str,
    station_id: str,
    user_id: str,
    expected_revision: int,
    starting_cue: int,
    max_cue: int,
    start_delay_ms: int,
    interval_ms: int,
) -> None:
    """Advance a Play All request with persisted CAS updates and broadcasts.

    Any manual command changes the revision/state and therefore stops this
    worker on its next boundary.  This keeps Hold/Clear/Next deterministic and
    prevents an older Play All task from overwriting newer operator intent.
    """
    targets = list(range(starting_cue + 1, max_cue + 1))
    if not targets:
        targets = [max_cue]

    for index, cue_index in enumerate(targets):
        delay_ms = start_delay_ms if index == 0 and starting_cue < 0 else interval_ms
        await asyncio.sleep(max(0, delay_ms) / 1000)
        current = await get_station_session(workspace_id, station_id)
        if (
            not current
            or current.get("session_revision") != expected_revision
            or current.get("state") != "live"
        ):
            return

        is_last = cue_index >= max_cue
        updated = await update_station_session_command(
            workspace_id=workspace_id,
            station_id=station_id,
            new_state="complete" if is_last else "live",
            new_cue_index=cue_index,
            expected_revision=expected_revision,
            user_id=user_id,
        )
        if not updated:
            return
        expected_revision = int(updated["session_revision"])
        await _broadcast_results_session(workspace_id, station_id, updated)


@router.get("/{id}/broadcast-state", summary="Get the station broadcast preview projection")
async def api_get_station_broadcast_state(
    id: str,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """Return the exact player/media projection rendered by OBS for the Editor."""
    from backend.core.broadcast_projection import get_station_broadcast_state

    state = await get_station_broadcast_state(id, principal.workspace_id)
    if not state:
        raise HTTPException(status_code=404, detail="Station not found")
    return state


@router.get("", summary="List all stations")
async def api_get_stations(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return all configured stream/station setups with their overlays. Auto-seeding default overlay if none exists."""
    stations = await get_stations(principal.workspace_id)

    # Pre-fetch all overlays to avoid N+1 query
    all_overlays = await get_all_station_overlays(principal.workspace_id)
    overlays_by_station = defaultdict(list)
    for overlay in all_overlays:
        overlays_by_station[overlay["station_id"]].append(overlay)

    for st in stations:
        storage_id = st.get("storage_id") or st["id"]
        overlays = overlays_by_station.get(storage_id, [])
        if not overlays:
            # Auto-seed a default overlay configuration for the station (Requirement 2 & 5 defaults)
            default_name = f"{st['id']}_default"
            default_config = {
                "background_url": "",
                "global_font_url": "",
                "global_font_family": "system-ui",
                "elements": {
                    "p1_name": { "id": "p1_name", "type": "text", "x": 400, "y": 950, "fontSize": 48, "color": "#ffffff", "text": "Player 1", "visible": True },
                    "p2_name": { "id": "p2_name", "type": "text", "x": 1520, "y": 950, "fontSize": 48, "color": "#ffffff", "text": "Player 2", "visible": True },
                    "p1_score": { "id": "p1_score", "type": "text", "x": 800, "y": 950, "fontSize": 64, "color": "#ff0000", "text": "0", "visible": True },
                    "p2_score": { "id": "p2_score", "type": "text", "x": 1120, "y": 950, "fontSize": 64, "color": "#ff0000", "text": "0", "visible": True },
                    "p1_prefix": { "id": "p1_prefix", "type": "text", "x": 400, "y": 900, "fontSize": 24, "color": "#aaaaaa", "text": "[PREFIX]", "visible": True },
                    "p2_prefix": { "id": "p2_prefix", "type": "text", "x": 1520, "y": 900, "fontSize": 24, "color": "#aaaaaa", "text": "[PREFIX]", "visible": True },
                    "tournament_round": { "id": "tournament_round", "type": "text", "x": 960, "y": 50, "fontSize": 32, "color": "#ffffff", "text": "Winners Semis", "visible": True },
                    "tournament_name": { "id": "tournament_name", "type": "text", "x": 960, "y": 100, "fontSize": 24, "color": "#aaaaaa", "text": "Tournament", "visible": True },
                    "p1_avatar": { "id": "p1_avatar", "type": "image", "x": 250, "y": 850, "width": 180, "height": 180, "src": "/static/player_placeholder.jpg", "visible": True },
                    "p2_avatar": { "id": "p2_avatar", "type": "image", "x": 1670, "y": 850, "width": 180, "height": 180, "src": "/static/player_placeholder.jpg", "visible": True },
                    "p1_flag": { "id": "p1_flag", "type": "image", "x": 250, "y": 980, "width": 120, "height": 80, "src": "/static/flag_placeholder.png", "visible": True },
                    "p2_flag": { "id": "p2_flag", "type": "image", "x": 1670, "y": 980, "width": 120, "height": 80, "src": "/static/flag_placeholder.png", "visible": True }
                }
            }
            import json
            from backend.core.database import save_overlay, add_station_overlay
            await save_overlay(default_name, json.dumps(default_config), principal.workspace_id)
            await add_station_overlay(storage_id, default_name, principal.workspace_id)
            await update_station_active_overlay(storage_id, default_name, principal.workspace_id)
            
            # Reload updated state
            overlays = await get_station_overlays(storage_id, principal.workspace_id)
            st["active_overlay"] = default_name

        st["overlays"] = overlays
    return {"stations": stations}


@router.post("",
             summary="Create a station")
async def api_create_station(body: CreateStationRequest, principal: SessionPrincipal = Depends(require_permission("station.manage"))):
    """Register a new station (OBS scene / stream setup)."""
    try:
        await require_workspace_capacity(principal.workspace_id, "stations")
    except EntitlementLimitExceeded as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await create_station(body.id, body.name, principal.workspace_id)
    return {"message": "Created"}


@router.patch("/{id}",
              summary="Update a station")
async def api_update_station(id: str, body: UpdateStationRequest, principal: SessionPrincipal = Depends(require_permission("station.manage"))):
    """Rename a station, toggle bot/hidden, set overlay, or remap stream binding."""
    fields = body.model_dump(exclude_unset=True)
    # Empty-string sentinels mean "clear" — store NULL.
    for k in ("startgg_stream_id", "stream_url", "active_overlay",
              "event_id", "room_name_or_id", "room_password"):
        if fields.get(k) == "":
            fields[k] = None
    if fields:
        await update_station(id, workspace_id=principal.workspace_id, **fields)
    return {"message": "Updated"}


@router.post("/{id}/broadcast-preview", summary="Show a not-started match on a broadcast station")
async def api_set_broadcast_preview(
    id: str,
    body: BroadcastPreviewRequest,
    principal: SessionPrincipal = Depends(require_permission("station.manage")),
):
    """Attach an existing NOT_STARTED provider/local match for preview only."""
    from backend.core.database import get_active_match, set_station_preview
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    # Preview uses the same local active-match projection as a live station.
    # The organizer must sync the tournament first so player links, avatars,
    # flags, and overrides are all present in one canonical row.
    match = await get_active_match(body.set_id, principal.workspace_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match is not in the Hub yet. Sync the tournament, then choose it again.")
    if str(match.get("status") or "").lower() != "not_started":
        raise HTTPException(status_code=409, detail="Only Not Started matches can be previewed")
    if station.get("active_match_id"):
        live_owner = await get_active_match(str(station["active_match_id"]), principal.workspace_id)
        if live_owner and str(live_owner.get("status") or "").lower() in {"called", "ready", "in_progress"}:
            raise HTTPException(status_code=409, detail="Station is already hosting a live match")
    if station.get("preview_match_id") and station.get("preview_match_id") != body.set_id:
        await set_station_preview(id, None, principal.workspace_id)
    updated = await set_station_preview(id, body.set_id, principal.workspace_id, match)
    from backend.api.ws_manager import manager as ws_manager
    await ws_manager.broadcast_to_slot(id, {"type": "match_update", "preview": True}, principal.workspace_id)
    return {"message": "Broadcast preview enabled", "station": updated, "match": match}


@router.delete("/{id}/broadcast-preview", summary="Clear a station broadcast preview")
async def api_clear_broadcast_preview(
    id: str,
    principal: SessionPrincipal = Depends(require_permission("station.manage")),
):
    from backend.core.database import set_station_preview
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    updated = await set_station_preview(id, None, principal.workspace_id)
    from backend.api.ws_manager import manager as ws_manager
    await ws_manager.broadcast_to_slot(id, {"type": "match_update", "preview": False}, principal.workspace_id)
    return {"message": "Broadcast preview cleared", "station": updated}


@router.delete("/{id}",
               summary="Delete a station")
async def api_delete_station(id: str, principal: SessionPrincipal = Depends(require_permission("station.manage"))):
    """Remove a station configuration."""
    await delete_station(id, principal.workspace_id)
    return {"message": "Deleted"}


@router.post("/{id}/overlay-access", summary="Rotate a revocable station or slide Browser Source link")
async def api_issue_overlay_access(
    id: str,
    body: IssueOverlayAccessRequest | None = Body(default=None),
    principal: SessionPrincipal = Depends(require_permission("overlay.manage")),
):
    from backend.core.overlay_access import issue_overlay_access
    try:
        token_id, token = await issue_overlay_access(
            principal.workspace_id,
            id,
            principal.user_id,
            body.overlay_name if body else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Fragment material is never sent in an HTTP request or server access log.
    return {"token_id": token_id, "url": f"/obs?slot={id}#access_token={token}"}


@router.delete("/overlay-access/{token_id}", status_code=204, summary="Revoke a Browser Source link")
async def api_revoke_overlay_access(token_id: str, principal: SessionPrincipal = Depends(require_permission("overlay.manage"))):
    from backend.core.overlay_access import revoke_overlay_access
    if not await revoke_overlay_access(principal.workspace_id, token_id):
        raise HTTPException(status_code=404, detail="Overlay link not found")


@router.post("/{id}/overlays",
             summary="Add overlay to station")
async def api_add_station_overlay(id: str, body: AddStationOverlayRequest, principal: SessionPrincipal = Depends(require_permission("overlay.manage"))):
    """Associate an overlay with this station."""
    station = await get_station(id, principal.workspace_id)
    if not station: raise ValueError("Station not found in workspace")
    await add_station_overlay(station["storage_id"], body.overlay_name, principal.workspace_id)
    return {"message": "Overlay added"}


@router.delete("/{id}/overlays/{overlay_name}",
               summary="Remove overlay from station")
async def api_remove_station_overlay(id: str, overlay_name: str, principal: SessionPrincipal = Depends(require_permission("overlay.manage"))):
    """Remove an overlay association from this station."""
    station = await get_station(id, principal.workspace_id)
    if not station: raise ValueError("Station not found in workspace")
    await remove_station_overlay(station["storage_id"], overlay_name, principal.workspace_id)
    return {"message": "Overlay removed"}


@router.post("/{id}/active-overlay",
             summary="Set active overlay for a station")
async def api_set_active_overlay(id: str, body: SetActiveOverlayRequest, principal: SessionPrincipal = Depends(require_permission("overlay.manage"))):
    """Set the currently loaded overlay preset for a station, broadcasting layout changes to OBS & the Editor."""
    station = await get_station(id, principal.workspace_id)
    if not station: raise ValueError("Station not found in workspace")
    await update_station_active_overlay(station["storage_id"], body.overlay_name, principal.workspace_id)
    
    # Broadcast overlay load to this station's WebSocket slot
    config = {}
    if body.overlay_name:
        from backend.core.database import get_overlays
        import json
        overlays = await get_overlays(principal.workspace_id)
        matched = next((o for o in overlays if o["name"] == body.overlay_name), None)
        if matched and matched.get("config"):
            try:
                cfg = matched["config"]
                config = json.loads(cfg) if isinstance(cfg, str) else cfg
            except Exception as e:
                print(f"Error parsing overlay config: {e}")
                
    from backend.api.ws_manager import manager as ws_manager
    await ws_manager.broadcast_to_slot(id, {
        "type": "overlay_loaded",
        "overlay_name": body.overlay_name,
        "config": config
    }, principal.workspace_id)
    
    return {"message": "Active overlay updated", "overlay_name": body.overlay_name}


@router.get("/{id}/queue", summary="Get matches queued on this station")
async def api_get_station_queue(id: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """List queued matches for this station with entrant details and player busy status."""
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    queue = await get_station_queue(id, principal.workspace_id)
    return {"queue": queue}


@router.post("/{id}/queue", summary="Add a match to station stream queue")
async def api_enqueue_station_match(
    id: str,
    body: EnqueueMatchRequest,
    principal: SessionPrincipal = Depends(require_permission("station.manage")),
):
    """Enqueue a match to the station's stream queue."""
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    queued = await enqueue_station_match(id, body.set_id, principal.workspace_id)
    if not queued:
        raise HTTPException(status_code=404, detail="Active match not found; refresh the bracket before queuing it")

    from backend.api.ws_manager import manager as ws_manager
    await ws_manager.broadcast({"type": "match_update", "_workspace_id": principal.workspace_id})
    await ws_manager.broadcast_to_slot(id, {"type": "match_update"}, principal.workspace_id)
    return {"message": "Match enqueued to station stream queue"}


@router.put("/{id}/queue/reorder", summary="Reorder matches in station stream queue")
async def api_reorder_station_queue(
    id: str,
    body: ReorderQueueRequest,
    principal: SessionPrincipal = Depends(require_permission("station.manage")),
):
    """Update order of matches in the station queue."""
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    await reorder_station_queue(id, body.set_ids, principal.workspace_id)

    from backend.api.ws_manager import manager as ws_manager
    await ws_manager.broadcast({"type": "match_update", "_workspace_id": principal.workspace_id})
    await ws_manager.broadcast_to_slot(id, {"type": "match_update"}, principal.workspace_id)
    return {"message": "Queue reordered"}


@router.delete("/{id}/queue/{set_id}", summary="Remove a match from station stream queue")
async def api_dequeue_station_match(
    id: str,
    set_id: str,
    principal: SessionPrincipal = Depends(require_permission("station.manage")),
):
    """Remove a match from the station stream queue."""
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    await dequeue_station_match(id, set_id, principal.workspace_id)

    from backend.api.ws_manager import manager as ws_manager
    await ws_manager.broadcast({"type": "match_update", "_workspace_id": principal.workspace_id})
    await ws_manager.broadcast_to_slot(id, {"type": "match_update"}, principal.workspace_id)
    return {"message": "Match removed from queue"}


@router.get(
    "/{id}/results-session",
    response_model=ResultsSessionResponse,
    summary="Read persisted results playback state",
)
async def api_get_station_results_session(
    id: str,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """Read the persisted station results playback session."""
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    session = await get_station_session(principal.workspace_id, id)
    if not session:
        return ResultsSessionResponse(
            station_id=id,
            media_output_id=None,
            state="cleared",
            cue_index=-1,
            session_revision=0,
            error_code=None,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    return ResultsSessionResponse(**session)


@router.put(
    "/{id}/results-session",
    response_model=ResultsSessionResponse,
    summary="Bind a frozen live output to the station in ready state",
)
async def api_bind_station_results_session(
    id: str,
    body: BindSessionRequest,
    principal: SessionPrincipal = Depends(require_permission("results.broadcast")),
):
    """Bind a frozen live media output to the station in ready state."""
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    media_output = await get_media_output(principal.workspace_id, body.media_output_id)
    if not media_output:
        raise HTTPException(status_code=404, detail="Media output not found")
    if media_output.get("output_kind") != "live":
        raise HTTPException(status_code=422, detail="Only a live results output can be bound to a station")

    version = await get_result_version_by_id(principal.workspace_id, media_output["result_version_id"])
    if not version or results_media.result_version_readiness(version) != "final":
        raise HTTPException(status_code=409, detail="The bound results version is not currently Final")
    scene_errors = results_media.validate_results_scene(
        media_output.get("scene_config") or {},
        version_id=version["id"],
        require_sequence=True,
    )
    if scene_errors:
        raise HTTPException(status_code=422, detail={"code": "invalid_results_scene", "errors": scene_errors})
    entries, _ = await get_version_entries(
        principal.workspace_id,
        version["id"],
        cutoff=media_output.get("cutoff", "top8"),
        page=media_output.get("page_number", 1),
        page_size=results_media.results_scene_page_size(media_output.get("scene_config")),
    )
    if not entries:
        raise HTTPException(status_code=422, detail="The bound results output has no cues")

    try:
        await enforce_auth_rate_limit(
            "results_overlay_bind",
            f"{principal.workspace_id}:{id}",
            limit=30,
            window_seconds=60,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail="Too many overlay binding requests. Slow down.") from exc

    bound = await bind_station_session(
        workspace_id=principal.workspace_id,
        station_id=id,
        media_output_id=body.media_output_id,
        expected_revision=body.expected_revision,
        user_id=principal.user_id,
    )
    if not bound:
        raise HTTPException(status_code=409, detail="Revision conflict")

    from backend.api.ws_manager import manager as ws_manager

    event = {
        "type": "results_session_update",
        "station_id": id,
        "session": {
            "media_output_id": bound["media_output_id"],
            "state": bound["state"],
            "cue_index": bound["cue_index"],
            "session_revision": bound["session_revision"],
            "updated_at": bound["updated_at"],
        },
    }
    await ws_manager.broadcast_to_slot(id, event, principal.workspace_id)
    await ws_manager.broadcast({**event, "_workspace_id": principal.workspace_id})

    await record_audit_event(
        workspace_id=principal.workspace_id,
        action="station.results_session.bind",
        outcome="success",
        actor_id=principal.user_id,
        target_type="station",
        target_id=id,
        detail={
            "media_output_id": body.media_output_id,
            "session_revision": bound["session_revision"],
        },
    )

    return ResultsSessionResponse(**bound)


@router.post(
    "/{id}/results-session/commands",
    response_model=ResultsSessionResponse,
    summary="Apply one idempotent playback command",
)
async def api_command_station_results_session(
    id: str,
    body: SessionCommandRequest,
    principal: SessionPrincipal = Depends(require_permission("results.broadcast")),
):
    """Apply one idempotent playback command to the station results session."""
    station = await get_station(id, principal.workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    current_session = await get_station_session(principal.workspace_id, id)
    if not current_session:
        current_session = {
            "station_id": id,
            "media_output_id": None,
            "state": "cleared",
            "cue_index": -1,
            "session_revision": 0,
        }

    try:
        await enforce_auth_rate_limit(
            "results_overlay_command",
            f"{principal.workspace_id}:{id}",
            limit=120,
            window_seconds=60,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail="Too many overlay commands. Slow down.") from exc

    cmd = body.command
    valid_states = {
        "take_live": {"ready", "held", "complete"},
        "play_all": {"ready", "live", "held", "complete"},
        "next": {"ready", "live", "held"},
        "previous": {"live", "held", "complete"},
        "hold": {"live"},
        "restart": {"ready", "live", "held", "complete"},
        "clear": {"ready", "live", "held", "complete", "error", "cleared"},
    }

    if current_session["state"] not in valid_states.get(cmd, set()):
        raise HTTPException(
            status_code=422,
            detail=f"Command '{cmd}' is invalid for state '{current_session['state']}'",
        )

    if cmd != "clear" and not current_session.get("media_output_id"):
        raise HTTPException(status_code=422, detail="No media output bound to station")

    max_cue = 0
    play_all_start_delay_ms = 300
    play_all_interval_ms = 800
    if current_session.get("media_output_id"):
        out = await get_media_output(principal.workspace_id, current_session["media_output_id"])
        if out:
            play_all_start_delay_ms, play_all_interval_ms = _results_sequence_timing(
                out.get("scene_config")
            )
            entries, _ = await get_version_entries(
                principal.workspace_id,
                out["result_version_id"],
                cutoff=out.get("cutoff", "top8"),
                page=out.get("page_number", 1),
                page_size=results_media.results_scene_page_size(out.get("scene_config")),
            )
            if entries:
                max_cue = max(0, len(entries) - 1)

    cur_cue = current_session.get("cue_index", -1)
    if cmd == "take_live":
        new_state = "live"
        new_cue = cur_cue
    elif cmd == "play_all":
        new_state = "live"
        new_cue = cur_cue
    elif cmd == "next":
        new_state = "complete" if cur_cue >= max_cue else "live"
        new_cue = min(max_cue, cur_cue + 1)
    elif cmd == "previous":
        new_state = "live" if current_session["state"] in ("live", "complete") else current_session["state"]
        new_cue = max(-1, cur_cue - 1)
    elif cmd == "hold":
        new_state = "held"
        new_cue = cur_cue
    elif cmd == "restart":
        new_state = "live"
        new_cue = -1
    elif cmd == "clear":
        new_state = "cleared"
        new_cue = -1
    else:
        raise HTTPException(status_code=422, detail=f"Unsupported command '{cmd}'")

    updated = await update_station_session_command(
        workspace_id=principal.workspace_id,
        station_id=id,
        new_state=new_state,
        new_cue_index=new_cue,
        expected_revision=body.expected_revision,
        user_id=principal.user_id,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Revision conflict")

    from backend.api.ws_manager import manager as ws_manager

    event = {
        "type": "results_session_update",
        "station_id": id,
        "session": {
            "media_output_id": updated["media_output_id"],
            "state": updated["state"],
            "cue_index": updated["cue_index"],
            "session_revision": updated["session_revision"],
            "updated_at": updated["updated_at"],
        },
    }
    await ws_manager.broadcast_to_slot(id, event, principal.workspace_id)
    await ws_manager.broadcast({**event, "_workspace_id": principal.workspace_id})

    await record_audit_event(
        workspace_id=principal.workspace_id,
        action=f"station.results_session.{cmd}",
        outcome="success",
        actor_id=principal.user_id,
        target_type="station",
        target_id=id,
        detail={
            "command": cmd,
            "new_state": updated["state"],
            "new_cue_index": updated["cue_index"],
            "session_revision": updated["session_revision"],
        },
    )

    if cmd == "play_all":
        task = asyncio.create_task(
            _run_results_play_all(
                workspace_id=principal.workspace_id,
                station_id=id,
                user_id=principal.user_id,
                expected_revision=int(updated["session_revision"]),
                starting_cue=int(updated["cue_index"]),
                max_cue=max_cue,
                start_delay_ms=play_all_start_delay_ms,
                interval_ms=play_all_interval_ms,
            )
        )
        _results_play_all_tasks.add(task)
        task.add_done_callback(_results_play_all_tasks.discard)

    return ResultsSessionResponse(**updated)
