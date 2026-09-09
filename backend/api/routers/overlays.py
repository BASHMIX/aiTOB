from fastapi import APIRouter, Depends, HTTPException
from backend.core.database import save_overlay, get_overlays, delete_overlay
from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import SaveOverlayRequest

router = APIRouter(tags=["overlays"])


@router.get("", summary="List all overlays")
async def api_get_overlays(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return all saved OBS overlay configurations."""
    return {"overlays": await get_overlays(principal.workspace_id)}


@router.post("",
             dependencies=[Depends(require_permission("overlay.manage"))],
             summary="Save an overlay configuration")
async def api_save_overlay(body: SaveOverlayRequest, principal: SessionPrincipal = Depends(require_permission("overlay.manage"))):
    """Create or update an OBS overlay by name with its full config."""
    try:
        await save_overlay(body.name, body.config, principal.workspace_id)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"message": "Saved"}


@router.delete("/{name}",
               dependencies=[Depends(require_permission("overlay.manage"))],
               summary="Delete an overlay configuration")
async def api_delete_overlay(name: str, principal: SessionPrincipal = Depends(require_permission("overlay.manage"))):
    """Delete a saved OBS overlay configuration by name."""
    await delete_overlay(name, principal.workspace_id)
    return {"message": "Deleted"}
