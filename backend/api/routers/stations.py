from fastapi import APIRouter, Depends, HTTPException
from collections import defaultdict
from backend.core.database import (
    get_stations, create_station, update_station, delete_station,
    add_station_overlay, remove_station_overlay, get_station_overlays,
    get_all_station_overlays, update_station_active_overlay, get_station
)
from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.core.entitlements import EntitlementLimitExceeded, require_workspace_capacity
from backend.api.schemas import (
    CreateStationRequest, UpdateStationRequest, AddStationOverlayRequest, SetActiveOverlayRequest,
    IssueOverlayAccessRequest,
)

router = APIRouter(tags=["stations"])


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
                    "p1_team": { "id": "p1_team", "type": "text", "x": 400, "y": 900, "fontSize": 24, "color": "#aaaaaa", "text": "[TEAM]", "visible": True },
                    "p2_team": { "id": "p2_team", "type": "text", "x": 1520, "y": 900, "fontSize": 24, "color": "#aaaaaa", "text": "[TEAM]", "visible": True },
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


@router.delete("/{id}",
               summary="Delete a station")
async def api_delete_station(id: str, principal: SessionPrincipal = Depends(require_permission("station.manage"))):
    """Remove a station configuration."""
    await delete_station(id, principal.workspace_id)
    return {"message": "Deleted"}


@router.post("/{id}/overlay-access", summary="Rotate a revocable station or slide Browser Source link")
async def api_issue_overlay_access(
    id: str,
    body: IssueOverlayAccessRequest | None = None,
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
