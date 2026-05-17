from fastapi import APIRouter, Request, Depends
import os
from backend.core.database import get_all_settings, set_setting, get_all_connections, set_connection
from backend.api.auth import verify_hub_password

router = APIRouter(tags=["settings"])


@router.get("/settings", summary="Get all app settings")
async def api_get_settings():
    """Return all persisted application settings."""
    return {"settings": await get_all_settings()}


@router.patch("/settings",
              dependencies=[Depends(verify_hub_password)],
              summary="Update app settings")
async def api_patch_settings(request: Request):
    """Update one or more settings (e.g. HUB_PASSWORD, tournament defaults)."""
    d = await request.json()
    for k, v in d.items():
        await set_setting(k, str(v))
    return {"message": "Settings updated"}


@router.get("/env", summary="Get environment/connection config")
async def api_get_env():
    """Return stored connection secrets (tokens, client IDs)."""
    return await get_all_connections()


@router.patch("/env",
              dependencies=[Depends(verify_hub_password)],
              summary="Update connection config")
async def api_patch_env(request: Request):
    """Update connection secrets (Start.gg token, Discord token, etc)."""
    d = await request.json()
    for k, v in d.items():
        if v:
            await set_connection(k, str(v))
    return {"message": "Environment updated"}


@router.post("/reconnect",
             dependencies=[Depends(verify_hub_password)],
             summary="Trigger service reconnection")
async def api_reconnect():
    """Signal services to reload configuration. Frontend will reload on response."""
    return {"message": "Reconnecting services..."}
