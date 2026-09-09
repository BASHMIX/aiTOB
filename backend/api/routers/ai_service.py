"""API-owned Organizer Assistant endpoints.

They never enqueue a Discord command.  A model call is made only for an
explicit organizer question or explicit connection test, never on page load.
"""
from fastapi import APIRouter, Depends, HTTPException

from backend.api.auth import require_permission, require_platform_admin
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import AIAssistantRequest, AIServiceConfigRequest, AIServiceSecretRequest
from backend.core.ai_service import (
    AIConfigurationError, AIService, AIServiceError, AIUsageLimitError,
    get_ai_config, migrate_legacy_ai_key, set_ai_api_key, test_ai_connection,
    update_ai_config,
)

router = APIRouter(tags=["ai-service"])
_service = AIService()


def _error(exc: AIServiceError) -> HTTPException:
    if isinstance(exc, AIUsageLimitError):
        return HTTPException(429, str(exc))
    if isinstance(exc, AIConfigurationError):
        return HTTPException(409, str(exc))
    return HTTPException(400, str(exc))


@router.get("/ai/config")
async def api_get_ai_config(principal: SessionPrincipal = Depends(require_platform_admin)):
    return await get_ai_config()


@router.patch("/ai/config")
async def api_patch_ai_config(body: AIServiceConfigRequest, principal: SessionPrincipal = Depends(require_platform_admin)):
    try:
        return await update_ai_config(body.model_dump(exclude_none=True))
    except AIServiceError as exc:
        raise _error(exc) from exc


@router.put("/ai/config/key")
async def api_set_ai_key(body: AIServiceSecretRequest, principal: SessionPrincipal = Depends(require_platform_admin)):
    try:
        await set_ai_api_key(body.api_key)
    except AIServiceError as exc:
        raise _error(exc) from exc
    return {"configured": True}


@router.post("/ai/config/migrate-legacy-key")
async def api_migrate_legacy_ai_key(principal: SessionPrincipal = Depends(require_platform_admin)):
    """Explicit migration only; it never deletes or exposes legacy material."""
    try:
        return await migrate_legacy_ai_key()
    except AIServiceError as exc:
        raise _error(exc) from exc


@router.post("/ai/config/test")
async def api_test_ai_connection(principal: SessionPrincipal = Depends(require_platform_admin)):
    # This is intentionally a deliberate admin action, not a settings refresh.
    return await test_ai_connection(_service)


@router.post("/ai/assistant/{tournament_slug:path}")
async def api_ask_assistant(tournament_slug: str, body: AIAssistantRequest, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    try:
        return await _service.answer(tournament_slug=tournament_slug, question=body.question, workspace_id=principal.workspace_id)
    except AIServiceError as exc:
        raise _error(exc) from exc
