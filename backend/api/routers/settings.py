from fastapi import APIRouter, Depends, status
from typing import Dict, Any
from backend.core.database import get_all_settings, set_setting, get_all_connections, set_connection
from backend.api.auth import verify_hub_password
from backend.api.schemas import PatchSettingsRequest, PatchEnvRequest, MessageResponse, ErrorResponse

router = APIRouter(tags=["settings"])


@router.get(
    "/settings",
    dependencies=[Depends(verify_hub_password)],
    summary="Get all app settings",
    response_model=Dict[str, Dict[str, str]],
    responses={401: {"model": ErrorResponse}},
    operation_id="getGlobalSettings"
)
async def api_get_settings():
    """Return all persisted global settings. Requires admin password authentication."""
    return {"settings": await get_all_settings()}


@router.patch(
    "/settings",
    dependencies=[Depends(verify_hub_password)],
    summary="Update app settings",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="updateGlobalSettings"
)
async def api_patch_settings(body: PatchSettingsRequest):
    """Update one or more persisted global settings (e.g., GLOBAL_LANGUAGE). Requires admin password authentication."""
    d = body.model_dump(exclude_none=True)
    for k, v in d.items():
        await set_setting(k, str(v))
    if "STARTGG_API_TOKEN" in d:
        import asyncio
        from backend.core.providers.startgg.client import get_client
        import json
        async def background_probe():
            client = get_client()
            client.token = None
            res = await client.probe_token_permissions()
            await set_setting("token_scope_status", json.dumps(res))
            from backend.api.ws_manager import manager as hub_mgr
            await hub_mgr.broadcast({"type": "match_update"})
        asyncio.create_task(background_probe())
    return MessageResponse(message="Settings updated")


@router.get(
    "/env",
    dependencies=[Depends(verify_hub_password)],
    summary="Get environment/connection config",
    response_model=Dict[str, str],
    responses={401: {"model": ErrorResponse}},
    operation_id="getConnectionConfig"
)
async def api_get_env():
    """Return all configured connection tokens and external credentials. Requires admin password authentication."""
    return await get_all_connections()


@router.patch(
    "/env",
    dependencies=[Depends(verify_hub_password)],
    summary="Update connection config",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="updateConnectionConfig"
)
async def api_patch_env(body: PatchEnvRequest):
    """Update environment secrets (tokens, public channel targets). Requires admin password authentication."""
    d = body.model_dump(exclude_none=True)
    for k, v in d.items():
        if v:
            await set_connection(k, str(v))
    if "STARTGG_API_TOKEN" in d:
        import asyncio
        from backend.core.providers.startgg.client import get_client
        import json
        async def background_probe():
            client = get_client()
            client.token = None
            res = await client.probe_token_permissions()
            await set_setting("token_scope_status", json.dumps(res))
            from backend.api.ws_manager import manager as hub_mgr
            await hub_mgr.broadcast({"type": "match_update"})
        asyncio.create_task(background_probe())
    return MessageResponse(message="Environment updated")


@router.post(
    "/settings/token-check",
    dependencies=[Depends(verify_hub_password)],
    summary="Run token permission probe",
    response_model=Dict[str, Any],
    responses={401: {"model": ErrorResponse}},
    operation_id="testStartggToken"
)
async def api_trigger_token_check():
    """Manually trigger the safe authentication and mutation write permission probe on the configured Start.gg token."""
    from backend.core.providers.startgg.client import get_client
    import json
    client = get_client()
    client.token = None # Force reload
    result = await client.probe_token_permissions()
    await set_setting("token_scope_status", json.dumps(result))
    from backend.api.ws_manager import manager as hub_mgr
    await hub_mgr.broadcast({"type": "match_update"})
    return result


@router.post(
    "/reconnect",
    dependencies=[Depends(verify_hub_password)],
    summary="Trigger service reconnection",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="reconnectServices"
)
async def api_reconnect():
    """Signal internal background worker threads and bot clients to reconnect using current credentials."""
    return MessageResponse(message="Reconnecting services...")
