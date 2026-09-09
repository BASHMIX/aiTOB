from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.core.providers.registry import get_provider
from backend.core.database import get_provider_usage
from backend.core.provider_projection import provider_capability_projection
from backend.core.challonge_resolution import resolution_service
from backend.core.provider_feature_flags import get_provider_feature_flags
from backend.core.providers.challonge.client import ChallongeError, ChallongeRateLimitError
from backend.api.schemas import ChallongeConnectionStateResponse, ChallongeResolveRequest, ChallongeResolveResponse

router = APIRouter(tags=["providers"])


def _workspace(principal: SessionPrincipal | object) -> str | None:
    """Keep direct service tests compatible while HTTP sessions stay scoped."""
    if getattr(principal, "legacy", False):
        return None
    return getattr(principal, "workspace_id", None)

@router.get("/{provider_type}/capabilities")
async def provider_capabilities(provider_type: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Local, non-secret capability declaration; never calls a provider API."""
    try:
        provider = get_provider(provider_type)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "provider_type": getattr(provider, "provider_type", provider_type),
        "display_name": provider.provider_name,
        **provider_capability_projection(provider),
    }


@router.get("/{provider_type}/usage")
async def provider_usage(provider_type: str, account_id: str | None = None, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    if provider_type != "challonge":
        raise HTTPException(400, "Usage tracking is currently available for Challonge only.")
    # Challonge documents 500 free requests/month. This is a local estimate,
    # not a claim that the provider has exposed its account-wide ledger.
    if account_id:
        from backend.core.integrations import get_integration_account
        if not await get_integration_account(account_id, workspace_id=_workspace(principal)):
            raise HTTPException(404, "Integration account not found")
    return await get_provider_usage("challonge", monthly_limit=500, workspace_id=_workspace(principal), provider_account_id=account_id)

@router.get("/challonge/connection", response_model=ChallongeConnectionStateResponse)
async def challonge_connection_state(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    flags = get_provider_feature_flags()
    from backend.core.integrations import configured_secret_types, list_integration_accounts
    connected = any(
        bool(await configured_secret_types(account["id"]) & {"access_token", "api_key"})
        for account in await list_integration_accounts(_workspace(principal))
        if account["provider_type"] == "challonge" and account["status"] == "active"
    )
    return ChallongeConnectionStateResponse(enabled=flags.challonge_read_enabled, connected=connected)


@router.post("/{provider_type}/tournaments/resolve", response_model=ChallongeResolveResponse)
async def resolve_tournament(provider_type: str, body: ChallongeResolveRequest, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    if provider_type != "challonge":
        raise HTTPException(400, "Preview is currently available for Challonge only.")
    if not get_provider_feature_flags().challonge_read_enabled:
        raise HTTPException(409, "Challonge read support is not enabled for this Hub.")
    from backend.core.integrations import get_integration_account
    workspace_id = _workspace(principal)
    # Legacy direct callers are kept compatible during staged ownership
    # migration; real account sessions must prove ownership of the account.
    if workspace_id is not None:
        account = await get_integration_account(body.provider_account_id, workspace_id=workspace_id)
        if not account or account.get("provider_type") != "challonge":
            raise HTTPException(404, "Challonge integration account not found")
    try:
        return await resolution_service.resolve(body.provider_account_id, body.identifier, body.subdomain)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ChallongeRateLimitError as exc:
        raise HTTPException(429, str(exc)) from exc
    except ChallongeError as exc:
        raise HTTPException(422, "Challonge request could not be completed.") from exc
    except Exception as exc:
        # Do not reflect a transport/provider exception: it can contain values
        # that must never appear in a browser payload or application log.
        raise HTTPException(502, "Challonge identity lookup failed.") from exc

@router.get("/{provider_type}/tournaments")
async def list_tournaments(provider_type: str, subdomain: Optional[str] = None, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    raise HTTPException(410, "Tournament enumeration is not available during identity-only import.")
