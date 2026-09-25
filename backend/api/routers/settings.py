from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any
from backend.core.database import (
    delete_connections, get_all_settings, set_setting, get_all_connections,
    get_connection, set_connection,
)
from backend.api.auth import require_global_settings_admin
from backend.api.schemas import PatchSettingsRequest, PatchEnvRequest, MessageResponse, ErrorResponse
from backend.core.email_delivery import public_email_status, send_email

router = APIRouter(tags=["settings"])


class EmailTestRequest(BaseModel):
    recipient: str = Field(min_length=3, max_length=254)
    message: str = Field(default="aiTOB email delivery test.", min_length=1, max_length=500)

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid recipient email is required")
        return value

_SECRET_KEYS = {
    "STARTGG_API_TOKEN", "STARTGG_CLIENT_SECRET", "CHALLONGE_API_KEY",
    "CHALLONGE_OAUTH_CLIENT_SECRET", "CHALLONGE_OAUTH_ACCESS_TOKEN",
    "CHALLONGE_OAUTH_REFRESH_TOKEN", "DISCORD_BOT_TOKEN", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "CLOUDINARY_URL",
    "HUB_PASSWORD", "hub_password", "RESEND_API_KEY", "SMTP_PASSWORD",
}

_MIGRATED_INTEGRATION_KEYS = {
    "DISCORD_BOT_TOKEN", "MATCH_CALL_CHANNEL_ID", "STARTGG_API_TOKEN",
    "STARTGG_CLIENT_ID", "STARTGG_CLIENT_SECRET", "STARTGG_OAUTH_REDIRECT_URI",
    "CHALLONGE_API_KEY",
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
        raise HTTPException(
            409,
            "Provider credentials are account-scoped and OAuth application credentials are deployment-owned. "
            "Use Integration Accounts or deployment configuration.",
        )
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
    """Reject the retired global-token probe."""
    raise HTTPException(410, "Global Start.gg tokens are retired. Test the Workspace integration account instead.")


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


@router.get(
    "/platform/email/status",
    dependencies=[Depends(require_global_settings_admin)],
    summary="Inspect email delivery configuration",
    operation_id="getEmailDeliveryStatus",
)
async def api_email_status():
    """Safe provider/from-address status; no API key or SMTP password is returned."""
    return public_email_status()


@router.post(
    "/platform/email/test",
    dependencies=[Depends(require_global_settings_admin)],
    summary="Send a platform-admin email delivery test",
    operation_id="sendEmailDeliveryTest",
)
async def api_email_test(body: EmailTestRequest):
    """Send only an explicit, plain-text test message through the configured provider."""
    sent = await send_email(
        recipient=str(body.recipient),
        subject="aiTOB email delivery test",
        text=body.message,
    )
    return {"sent": sent, "status": public_email_status()}
