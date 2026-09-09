from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from backend.core.database import (
    delete_connections, get_all_settings, set_setting, get_all_connections,
    get_connection, set_connection,
)
from backend.api.auth import require_global_settings_admin
from backend.api.schemas import PatchSettingsRequest, PatchEnvRequest, MessageResponse, ErrorResponse

router = APIRouter(tags=["settings"])

_SECRET_KEYS = {
    "STARTGG_API_TOKEN", "STARTGG_CLIENT_SECRET", "CHALLONGE_API_KEY",
    "CHALLONGE_OAUTH_CLIENT_SECRET", "CHALLONGE_OAUTH_ACCESS_TOKEN",
    "CHALLONGE_OAUTH_REFRESH_TOKEN", "DISCORD_BOT_TOKEN", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "CLOUDINARY_URL",
    "HUB_PASSWORD", "hub_password",
}

_MIGRATED_INTEGRATION_KEYS = {
    "DISCORD_BOT_TOKEN", "MATCH_CALL_CHANNEL_ID", "CHALLONGE_API_KEY",
    "CHALLONGE_OAUTH_CLIENT_ID", "CHALLONGE_OAUTH_CLIENT_SECRET",
    "CHALLONGE_OAUTH_REDIRECT_URI", "CHALLONGE_OAUTH_ACCESS_TOKEN",
    "CHALLONGE_OAUTH_REFRESH_TOKEN", "CHALLONGE_OAUTH_EXPIRES_AT",
}


@router.get(
    "/settings",
    dependencies=[Depends(require_global_settings_admin)],
    summary="Get all app settings",
    response_model=Dict[str, Dict[str, str]],
    responses={401: {"model": ErrorResponse}},
    operation_id="getGlobalSettings"
)
async def api_get_settings():
    """Return all persisted global settings. Requires admin password authentication."""
    return {"settings": {key: value for key, value in (await get_all_settings()).items() if key not in _SECRET_KEYS}}


@router.patch(
    "/settings",
    dependencies=[Depends(require_global_settings_admin)],
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
    dependencies=[Depends(require_global_settings_admin)],
    summary="Get environment/connection config",
    response_model=Dict[str, str],
    responses={401: {"model": ErrorResponse}},
    operation_id="getConnectionConfig"
)
async def api_get_env():
    """Return all configured connection tokens and external credentials. Requires admin password authentication."""
    values = await get_all_connections()
    # The UI needs only a configured/not-configured indicator for provider keys.
    # Never return a Challonge key back to the browser after it has been saved.
    for key in (
        "STARTGG_API_TOKEN",
        "STARTGG_CLIENT_SECRET",
        "CHALLONGE_API_KEY",
        "CHALLONGE_OAUTH_CLIENT_SECRET",
        "CHALLONGE_OAUTH_ACCESS_TOKEN",
        "CHALLONGE_OAUTH_REFRESH_TOKEN", "DISCORD_BOT_TOKEN", "GEMINI_API_KEY",
        "GOOGLE_API_KEY", "CLOUDINARY_URL",
    ):
        if values.get(key):
            values[key] = "configured"
    return values


@router.patch(
    "/env",
    dependencies=[Depends(require_global_settings_admin)],
    summary="Update connection config",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="updateConnectionConfig"
)
async def api_patch_env(body: PatchEnvRequest):
    """Update environment secrets (tokens, public channel targets). Requires admin password authentication."""
    d = body.model_dump(exclude_none=True)
    attempted_legacy = sorted(key for key in d if key in _MIGRATED_INTEGRATION_KEYS)
    if attempted_legacy:
        raise HTTPException(409, "Provider and Discord credentials are account-scoped. Use Integration Accounts.")
    secret_keys = {
        "STARTGG_API_TOKEN", "STARTGG_CLIENT_SECRET", "CHALLONGE_API_KEY",
        "CHALLONGE_OAUTH_CLIENT_SECRET", "CHALLONGE_OAUTH_ACCESS_TOKEN",
        "CHALLONGE_OAUTH_REFRESH_TOKEN",
    }
    oauth_config_keys = {
        "CHALLONGE_OAUTH_CLIENT_ID", "CHALLONGE_OAUTH_CLIENT_SECRET", "CHALLONGE_OAUTH_REDIRECT_URI",
    }
    oauth_changed = False
    for k, v in d.items():
        # Redacted values returned by GET /env must never overwrite a real
        # credential when the user saves an unrelated connection setting.
        if v and not (k in secret_keys and v == "configured"):
            if k in oauth_config_keys and await get_connection(k) != str(v):
                oauth_changed = True
            await set_connection(k, str(v))
    # An authorization is issued for one client configuration. If the client,
    # secret, or callback changes, never present a token from the previous app
    # as a successful connection.
    if oauth_changed:
        await delete_connections([
            "CHALLONGE_OAUTH_ACCESS_TOKEN", "CHALLONGE_OAUTH_REFRESH_TOKEN", "CHALLONGE_OAUTH_EXPIRES_AT",
        ])
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
    dependencies=[Depends(require_global_settings_admin)],
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
    dependencies=[Depends(require_global_settings_admin)],
    summary="Trigger service reconnection",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="reconnectServices"
)
async def api_reconnect():
    """Signal internal background worker threads and bot clients to reconnect using current credentials."""
    return MessageResponse(message="Reconnecting services...")
