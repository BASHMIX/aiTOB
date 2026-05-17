from fastapi import APIRouter, HTTPException, Depends
from backend.core.database import save_overlay, get_overlays, delete_overlay
from backend.api.auth import verify_hub_password
from backend.api.schemas import SaveOverlayRequest

router = APIRouter(tags=["overlays"])


@router.get("", summary="List all overlays")
async def api_get_overlays():
    """Return all saved OBS overlay configurations."""
    return {"overlays": await get_overlays()}


@router.post("",
             dependencies=[Depends(verify_hub_password)],
             summary="Save an overlay configuration")
async def api_save_overlay(body: SaveOverlayRequest):
    """Create or update an OBS overlay by name with its full config."""
    await save_overlay(body.name, body.config)
    return {"message": "Saved"}
