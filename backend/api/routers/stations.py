from fastapi import APIRouter, HTTPException, Depends
from backend.core.database import (
    get_stations, create_station, update_station, delete_station,
    add_station_overlay, remove_station_overlay, get_station_overlays,
    update_station_active_overlay
)
from backend.api.auth import verify_hub_password
from backend.api.schemas import (
    CreateStationRequest, UpdateStationRequest, AddStationOverlayRequest, SetActiveOverlayRequest
)

router = APIRouter(tags=["stations"])


@router.get("", summary="List all stations")
async def api_get_stations():
    """Return all configured stream/station setups with their overlays. Auto-seeding default overlay if none exists."""
    stations = await get_stations()
    for st in stations:
        overlays = await get_station_overlays(st["id"])
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
            await save_overlay(default_name, json.dumps(default_config))
            await add_station_overlay(st["id"], default_name)
            await update_station_active_overlay(st["id"], default_name)
            
            # Reload updated state
            overlays = await get_station_overlays(st["id"])
            st["active_overlay"] = default_name

        st["overlays"] = overlays
    return {"stations": stations}


@router.post("",
             dependencies=[Depends(verify_hub_password)],
             summary="Create a station")
async def api_create_station(body: CreateStationRequest):
    """Register a new station (OBS scene / stream setup)."""
    await create_station(body.id, body.name)
    return {"message": "Created"}


@router.patch("/{id}",
              dependencies=[Depends(verify_hub_password)],
              summary="Update a station")
async def api_update_station(id: str, body: UpdateStationRequest):
    """Rename a station, toggle bot/hidden, set overlay, or remap stream binding."""
    fields = body.model_dump(exclude_unset=True)
    # Empty-string sentinels mean "clear" — store NULL.
    for k in ("startgg_stream_id", "stream_url", "active_overlay"):
        if fields.get(k) == "":
            fields[k] = None
    if fields:
        await update_station(id, **fields)
    return {"message": "Updated"}


@router.delete("/{id}",
               dependencies=[Depends(verify_hub_password)],
               summary="Delete a station")
async def api_delete_station(id: str):
    """Remove a station configuration."""
    await delete_station(id)
    return {"message": "Deleted"}


@router.post("/{id}/overlays",
             dependencies=[Depends(verify_hub_password)],
             summary="Add overlay to station")
async def api_add_station_overlay(id: str, body: AddStationOverlayRequest):
    """Associate an overlay with this station."""
    await add_station_overlay(id, body.overlay_name)
    return {"message": "Overlay added"}


@router.delete("/{id}/overlays/{overlay_name}",
               dependencies=[Depends(verify_hub_password)],
               summary="Remove overlay from station")
async def api_remove_station_overlay(id: str, overlay_name: str):
    """Remove an overlay association from this station."""
    await remove_station_overlay(id, overlay_name)
    return {"message": "Overlay removed"}


@router.post("/{id}/active-overlay",
             dependencies=[Depends(verify_hub_password)],
             summary="Set active overlay for a station")
async def api_set_active_overlay(id: str, body: SetActiveOverlayRequest):
    """Set the currently loaded overlay preset for a station, broadcasting layout changes to OBS & the Editor."""
    await update_station_active_overlay(id, body.overlay_name)
    
    # Broadcast overlay load to this station's WebSocket slot
    config = {}
    if body.overlay_name:
        from backend.core.database import get_overlays
        import json
        overlays = await get_overlays()
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
    })
    
    return {"message": "Active overlay updated", "overlay_name": body.overlay_name}
