"""Admin-only account-scoped integration configuration.

Secret-bearing inputs are accepted only for immediate encryption and every response
is a safe projection: there is intentionally no secret read endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import (
    IntegrationAccountRequest, IntegrationCredentialRequest,
    IntegrationDestinationRequest, IntegrationOAuthApplicationRequest, ProviderIdentityLinkRequest,
    ProviderCredentialConnectRequest,
)
from backend.core.identity_links import save_identity_override
from backend.core.integrations import (
    IntegrationAccountInUse, IntegrationError, configured_secret_types,
    create_integration_account, add_integration_destination, create_oauth_application,
    disable_integration_account, list_integration_accounts, set_integration_secret,
    get_integration_account, list_integration_destinations,
    enable_integration_account, remove_integration_secret,
    update_integration_account,
)
from backend.core.entitlements import EntitlementLimitExceeded, require_workspace_capacity
from backend.core.discord_resources import permission_checks
from backend.core.discord_api import DiscordAPIError, discover_guild, send_test_message
from backend.core.tournament_templates import render_message, TemplateError
from backend.core.provider_credentials import ProviderCredentialError, verify_provider_credential

router = APIRouter(tags=["integrations"])


@router.get("/integrations")
async def list_accounts(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    accounts = await list_integration_accounts(principal.workspace_id)
    safe = []
    for account in accounts:
        secret_types = await configured_secret_types(account["id"])
        metadata = account.get("metadata") or {}
        configured = (
            bool(metadata.get("installation_verified"))
            if account.get("provider_type") == "discord"
            else bool(secret_types)
        )
        safe.append({
            **account,
            "configured": configured,
            "credential_types": sorted(secret_types),
            "destinations": await list_integration_destinations(account["id"], workspace_id=principal.workspace_id),
        })
    return {"accounts": safe}


@router.post("/integrations", status_code=status.HTTP_201_CREATED)
async def create_account(body: IntegrationAccountRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    if body.provider_type == "discord":
        raise HTTPException(422, "Use the managed Discord installation flow")
    raise HTTPException(422, "Use the verified BYOC provider credential flow")


@router.post("/integrations/oauth-applications", status_code=status.HTTP_201_CREATED)
async def create_application(body: IntegrationOAuthApplicationRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    if not body.redirect_uri.startswith("https://"):
        raise HTTPException(422, "OAuth callback must use HTTPS.")
    try:
        return await create_oauth_application(principal.workspace_id, body.provider_type, body.client_id, body.redirect_uri, body.client_secret)
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/integrations/provider-credentials/connect")
async def connect_provider_credential(
    body: ProviderCredentialConnectRequest,
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    """Verify and store one workspace-owned provider credential.

    Identity is always read from the provider. The organizer never supplies an
    account id or display name, preventing a local label from masquerading as
    the credential owner.
    """

    try:
        verified = await verify_provider_credential(body.provider_type, body.credential)
    except ProviderCredentialError as exc:
        raise HTTPException(422, str(exc)) from exc

    accounts = await list_integration_accounts(principal.workspace_id)
    account = next(
        (
            item for item in accounts
            if item["provider_type"] == verified.provider_type
            and item["external_account_id"] == verified.external_account_id
        ),
        None,
    )
    if account is None:
        legacy_accounts = [
            item for item in accounts
            if item["provider_type"] == verified.provider_type
            and item["external_account_id"] == "legacy"
        ]
        # Preserve tournament bindings created by the one-time credential
        # migration. An ambiguous legacy set is never guessed.
        if len(legacy_accounts) == 1:
            account = legacy_accounts[0]
    try:
        if account is None:
            await require_workspace_capacity(principal.workspace_id, "integrations")
            account = await create_integration_account(
                principal.workspace_id,
                verified.provider_type,
                verified.external_account_id,
                verified.display_name,
                metadata=verified.metadata,
            )
        else:
            account = await update_integration_account(
                str(account["id"]),
                workspace_id=principal.workspace_id,
                external_account_id=verified.external_account_id,
                display_name=verified.display_name,
                metadata=verified.metadata,
            )
            if account.get("status") == "disabled":
                account = await enable_integration_account(
                    str(account["id"]), workspace_id=principal.workspace_id
                )
        await set_integration_secret(
            str(account["id"]),
            verified.secret_type,
            body.credential.strip(),
            workspace_id=principal.workspace_id,
        )
    except EntitlementLimitExceeded as exc:
        raise HTTPException(409, str(exc)) from exc
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "ok": True,
        "account": account,
        "configured": True,
        "credential_owner": "workspace",
    }


@router.post("/integrations/{account_id}/credentials")
async def rotate_credential(account_id: str, body: IntegrationCredentialRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    account = await get_integration_account(account_id, workspace_id=principal.workspace_id)
    if not account:
        raise HTTPException(404, "Integration account not found")
    if account.get("provider_type") == "discord":
        raise HTTPException(422, "Discord uses the platform-managed bot; customer bot tokens are not accepted")
    if account.get("provider_type") in {"startgg", "challonge"}:
        try:
            verified = await verify_provider_credential(str(account["provider_type"]), body.secret)
        except ProviderCredentialError as exc:
            raise HTTPException(422, str(exc)) from exc
        if verified.external_account_id != str(account.get("external_account_id") or ""):
            raise HTTPException(409, "This credential belongs to a different provider account. Connect it as a separate account.")
        if body.secret_type != verified.secret_type:
            raise HTTPException(422, "Credential type does not match the selected provider.")
    try:
        await set_integration_secret(account_id, body.secret_type, body.secret, workspace_id=principal.workspace_id)
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True, "configured": True}


@router.post("/integrations/{account_id}/destinations")
async def add_destination(account_id: str, body: IntegrationDestinationRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    account = await get_integration_account(account_id, workspace_id=principal.workspace_id)
    if not account:
        raise HTTPException(404, "Integration account not found")
    if account.get("provider_type") == "discord":
        raise HTTPException(422, "Use the verified Discord destination endpoint")
    try:
        return await add_integration_destination(account_id, body.destination_type, body.external_id, body.display_name, workspace_id=principal.workspace_id)
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/integrations/{account_id}/disable")
async def disable_account(account_id: str, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    try:
        await disable_integration_account(account_id, workspace_id=principal.workspace_id)
    except IntegrationAccountInUse as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "status": "disabled"}


@router.post("/integrations/{account_id}/enable")
async def enable_account(account_id: str, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    try:
        return await enable_integration_account(account_id, workspace_id=principal.workspace_id)
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/integrations/{account_id}/credentials/{secret_type}")
async def remove_credential(account_id: str, secret_type: str, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    account = await get_integration_account(account_id, workspace_id=principal.workspace_id)
    if not account:
        raise HTTPException(404, "Integration account not found")
    if account.get("provider_type") == "discord":
        raise HTTPException(422, "Discord uses the platform-managed bot and has no customer credential")
    try:
        await remove_integration_secret(account_id, secret_type, workspace_id=principal.workspace_id)
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True, "status": "missing"}


@router.get("/integrations/{account_id}/discord/resources")
async def discord_resources(account_id: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    account = await get_integration_account(account_id, workspace_id=principal.workspace_id)
    if not account or account.get("provider_type") != "discord":
        raise HTTPException(404, "Discord connection not found")
    try:
        discovered = await discover_guild(str(account["external_account_id"]))
    except DiscordAPIError as exc:
        raise HTTPException(502, str(exc)) from exc
    channels = []
    for channel in discovered["channels"]:
        channels.append({
            **{key: channel.get(key) for key in ("id", "name", "type", "parent_id")},
            "permissions": permission_checks(channel.get("permissions") or {}),
            "ready": all((channel.get("permissions") or {}).values()),
        })
    return {
        "guilds": [discovered["guild"]],
        "channels": channels,
        "roles": discovered["roles"],
    }


@router.post("/integrations/{account_id}/discord/recheck")
async def discord_recheck(account_id: str, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    return await discord_resources(account_id, principal)


@router.post("/integrations/{account_id}/discord/destinations")
async def save_discord_destination(
    account_id: str,
    body: dict[str, str],
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    account = await __import__("backend.core.integrations", fromlist=["get_integration_account"]).get_integration_account(
        account_id, workspace_id=principal.workspace_id,
    )
    if not account or account.get("provider_type") != "discord":
        raise HTTPException(404, "Discord connection not found")
    destination_type = str(body.get("destination_type") or "match_call_channel")
    if destination_type not in {"match_call_channel", "escalation_channel", "registration_channel"}:
        raise HTTPException(422, "Unsupported Discord destination type")
    channel_id = str(body.get("channel_id") or "").strip()
    resources = await discord_resources(account_id, principal)
    channel = next((item for item in resources["channels"] if str(item["id"]) == channel_id), None)
    if not channel:
        raise HTTPException(422, "Channel is not part of the connected Discord server")
    if not channel.get("ready"):
        raise HTTPException(422, "The aiTOB bot is missing required permissions in this channel")
    try:
        return await add_integration_destination(
            account_id, destination_type, channel_id,
            str(channel.get("name") or "Discord channel"), workspace_id=principal.workspace_id,
        )
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/integrations/{account_id}/discord/test-message")
async def discord_test_message(
    account_id: str,
    body: dict[str, str],
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    channel_id = str(body.get("channel_id") or "").strip()
    resources = await discord_resources(account_id, principal)
    channel = next((item for item in resources["channels"] if str(item["id"]) == channel_id), None)
    if not channel or not channel.get("ready"):
        raise HTTPException(422, "Select a channel where aiTOB has all required permissions")
    try:
        message_id = await send_test_message(channel_id)
    except DiscordAPIError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True, "message_id": message_id, "channel_id": channel_id}


@router.post("/tournament-setup/drafts/{draft_id}/discord/template-preview")
async def discord_template_preview(draft_id: str, body: dict[str, object], principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    from backend.core.tournament_setup import get_draft, DraftNotFound
    try:
        draft = await get_draft(draft_id, principal.workspace_id)
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    key = str(body.get("template_key") or "match_call")
    template = body.get("template")
    values = {"player_1": "Player One", "player_2": "Player Two", "destination": "#matches", "tournament": (draft.get("tournament_review") or {}).get("display_name") or "Tournament", "round": "Round 1", "match_id": "preview"}
    try:
        rendered = render_message(key, values, templates={key: str(template)} if template is not None else None)
    except TemplateError as exc:
        raise HTTPException(422, {"code": str(exc), "retryable": False}) from exc
    return {"template_key": key, "rendered": rendered, "variables": sorted(values)}


@router.put("/integrations/identity-links")
async def save_identity_link(body: ProviderIdentityLinkRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    return await save_identity_override(body.model_dump(exclude_none=True), principal.workspace_id)
