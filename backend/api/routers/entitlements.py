"""Platform-admin manual entitlement controls.

These endpoints are an explicit local administration tool, not a payment
gateway.  They never contact a provider and never expose payment credentials.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.auth import require_platform_admin
from backend.core.entitlements import apply_manual_subscription, get_workspace_entitlement
from backend.core.workspace_auth import SessionPrincipal

router = APIRouter(prefix="/platform/workspaces", tags=["entitlements"])


class ManualSubscriptionRequest(BaseModel):
    action: Literal["activate", "extend", "suspend"]
    plan_key: Literal["free", "managed"] | None = None
    expires_at: str | None = Field(default=None, max_length=80)
    extend_days: int | None = Field(default=None, ge=1, le=3650)


@router.get("/{workspace_id}/subscription")
async def subscription(workspace_id: str, principal: SessionPrincipal = Depends(require_platform_admin)):
    try:
        return await get_workspace_entitlement(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{workspace_id}/subscription")
async def manual_subscription(
    workspace_id: str,
    body: ManualSubscriptionRequest,
    principal: SessionPrincipal = Depends(require_platform_admin),
):
    try:
        return await apply_manual_subscription(
            workspace_id,
            actor_user_id=principal.user_id,
            action=body.action,
            plan_key=body.plan_key,
            expires_at=body.expires_at,
            extend_days=body.extend_days,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

