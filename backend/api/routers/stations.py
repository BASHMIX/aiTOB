from fastapi import APIRouter, HTTPException, Depends
from backend.core.database import get_stations, create_station, update_station, delete_station, add_station_overlay, remove_station_overlay, get_station_overlays
from backend.api.auth import verify_hub_password
from backend.api.schemas import CreateStationRequest, UpdateStationRequest, AddStationOverlayRequest

router = APIRouter(tags=["stations"])


@router.get("", summary="List all stations")
async def api_get_stations():
    """Return all configured stream/station setups with their overlays."""
    stations = await get_stations()
    for st in stations:
        st["overlays"] = await get_station_overlays(st["id"])
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
    """Rename or reconfigure a station."""
    await update_station(id, body.name)
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
