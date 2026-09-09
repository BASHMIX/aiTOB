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
)
from backend.core.identity_links import save_identity_override
from backend.core.integrations import (
    IntegrationAccountInUse, IntegrationError, configured_secret_types,
    create_integration_account, add_integration_destination, create_oauth_application,
    disable_integration_account, list_integration_accounts, set_integration_secret,
    list_integration_destinations,
)
from backend.core.entitlements import EntitlementLimitExceeded, require_workspace_capacity

router = APIRouter(tags=["integrations"])


@router.get("/integrations")
async def list_accounts(principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    accounts = await list_integration_accounts(principal.workspace_id)
    safe = []
    for account in accounts:
        secret_types = await configured_secret_types(account["id"])
        safe.append({
            **account,
            "configured": bool(secret_types),
            "credential_types": sorted(secret_types),
            "destinations": await list_integration_destinations(account["id"], workspace_id=principal.workspace_id),
        })
    return {"accounts": safe}


@router.post("/integrations", status_code=status.HTTP_201_CREATED)
async def create_account(body: IntegrationAccountRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    try:
        await require_workspace_capacity(principal.workspace_id, "integrations")
        return await create_integration_account(principal.workspace_id, body.provider_type, body.external_account_id, body.display_name, metadata=body.metadata)
    except EntitlementLimitExceeded as exc:
        raise HTTPException(409, str(exc)) from exc
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/integrations/oauth-applications", status_code=status.HTTP_201_CREATED)
async def create_application(body: IntegrationOAuthApplicationRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    if not body.redirect_uri.startswith("https://"):
        raise HTTPException(422, "OAuth callback must use HTTPS.")
    try:
        return await create_oauth_application(principal.workspace_id, body.provider_type, body.client_id, body.redirect_uri, body.client_secret)
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/integrations/{account_id}/credentials")
async def rotate_credential(account_id: str, body: IntegrationCredentialRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    try:
        await set_integration_secret(account_id, body.secret_type, body.secret, workspace_id=principal.workspace_id)
    except IntegrationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True, "configured": True}


@router.post("/integrations/{account_id}/destinations")
async def add_destination(account_id: str, body: IntegrationDestinationRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
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


@router.put("/integrations/identity-links")
async def save_identity_link(body: ProviderIdentityLinkRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    return await save_identity_override(body.model_dump(exclude_none=True), principal.workspace_id)
