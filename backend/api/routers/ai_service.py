"""API-owned Organizer Assistant endpoints.

They never enqueue a Discord command.  A model call is made only for an
explicit organizer question or explicit connection test, never on page load.
"""
from fastapi import APIRouter, Depends, HTTPException

from backend.api.auth import require_permission, require_platform_admin
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import AIAssistantRequest, AIServiceConfigRequest, AIServiceSecretRequest, AIConnectionTestRequest
from backend.core.ai_service import (
    AIConfigurationError, AIService, AIServiceError, AIUsageLimitError,
    get_ai_config, migrate_legacy_ai_key, set_ai_api_key, test_ai_connection,
    update_ai_config, update_workspace_ai_config, set_workspace_ai_key,
)
from backend.core import integrations

router = APIRouter(tags=["ai-service"])
_service = AIService()


def _error(exc: AIServiceError) -> HTTPException:
    if isinstance(exc, AIUsageLimitError):
        return HTTPException(429, str(exc))
    if isinstance(exc, AIConfigurationError):
        return HTTPException(409, str(exc))
    return HTTPException(400, str(exc))


@router.get("/ai/config")
async def api_get_ai_config(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    return await get_ai_config(principal.workspace_id)


@router.patch("/ai/config")
async def api_patch_ai_config(body: AIServiceConfigRequest, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    try:
        return await update_workspace_ai_config(principal.workspace_id, body.model_dump(exclude_none=True), actor_id=principal.user_id)
    except AIServiceError as exc:
        raise _error(exc) from exc


@router.put("/ai/config/key")
async def api_set_ai_key(body: AIServiceSecretRequest, principal: SessionPrincipal = Depends(require_platform_admin)):
    try:
        await set_ai_api_key(body.api_key)
    except AIServiceError as exc:
        raise _error(exc) from exc
    return {"configured": True}


@router.put("/ai/connections/{provider}/credential")
async def api_set_workspace_ai_key(
    provider: str, body: AIServiceSecretRequest,
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    try:
        return await set_workspace_ai_key(
            principal.workspace_id, provider, body.api_key, actor_id=principal.user_id
        )
    except (AIServiceError, integrations.IntegrationError) as exc:
        raise _error(exc) from exc


async def _workspace_provider_account(principal: SessionPrincipal, provider: str) -> dict:
    config = await get_ai_config(principal.workspace_id)
    card = (config.get("connections") or {}).get(provider)
    if not card or not card.get("account_id"):
        raise HTTPException(404, "AI connection not found")
    account = await integrations.get_integration_account(
        str(card["account_id"]), workspace_id=principal.workspace_id, active_only=False
    )
    if not account or account.get("provider_type") != provider:
        raise HTTPException(404, "AI connection not found")
    return account


@router.post("/ai/connections/{provider}/test")
async def api_test_workspace_ai_connection(
    provider: str, body: AIConnectionTestRequest | None = None,
    principal: SessionPrincipal = Depends(require_permission("integrations.manage")),
):
    try:
        if body and body.model:
            await update_workspace_ai_config(principal.workspace_id, {"model": body.model}, actor_id=principal.user_id)
        return await test_ai_connection(_service, workspace_id=principal.workspace_id, provider_type=provider)
    except AIServiceError as exc:
        raise _error(exc) from exc


@router.post("/ai/connections/{provider}/enable")
async def api_enable_workspace_ai_connection(
    provider: str, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))
):
    try:
        account = await _workspace_provider_account(principal, provider)
        await integrations.enable_integration_account(str(account["id"]), workspace_id=principal.workspace_id)
        return await get_ai_config(principal.workspace_id)
    except (AIServiceError, integrations.IntegrationError) as exc:
        raise _error(exc) from exc


@router.post("/ai/connections/{provider}/disable")
async def api_disable_workspace_ai_connection(
    provider: str, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))
):
    try:
        account = await _workspace_provider_account(principal, provider)
        await integrations.disable_integration_account(str(account["id"]), workspace_id=principal.workspace_id)
        return await get_ai_config(principal.workspace_id)
    except (AIServiceError, integrations.IntegrationError) as exc:
        raise _error(exc) from exc


@router.delete("/ai/connections/{provider}/credential")
async def api_remove_workspace_ai_key(
    provider: str, principal: SessionPrincipal = Depends(require_permission("integrations.manage"))
):
    try:
        account = await _workspace_provider_account(principal, provider)
        await integrations.remove_integration_secret(
            str(account["id"]), "api_key", workspace_id=principal.workspace_id
        )
        return await get_ai_config(principal.workspace_id)
    except (AIServiceError, integrations.IntegrationError) as exc:
        raise _error(exc) from exc


@router.post("/ai/config/migrate-legacy-key")
async def api_migrate_legacy_ai_key(principal: SessionPrincipal = Depends(require_platform_admin)):
    """Explicit migration only; it never deletes or exposes legacy material."""
    try:
        return await migrate_legacy_ai_key()
    except AIServiceError as exc:
        raise _error(exc) from exc


@router.post("/ai/config/test")
async def api_test_ai_connection(principal: SessionPrincipal = Depends(require_permission("integrations.manage"))):
    # This is intentionally a deliberate admin action, not a settings refresh.
    return await test_ai_connection(_service, workspace_id=principal.workspace_id)


@router.post("/ai/assistant/{tournament_slug:path}")
async def api_ask_assistant(tournament_slug: str, body: AIAssistantRequest, principal: SessionPrincipal = Depends(require_permission("assistant.use"))):
    try:
        return await _service.answer(tournament_slug=tournament_slug, question=body.question, workspace_id=principal.workspace_id)
    except AIServiceError as exc:
        raise _error(exc) from exc
