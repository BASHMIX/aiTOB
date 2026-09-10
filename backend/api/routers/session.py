"""Session endpoints; public registration is implemented but closed by default."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from backend.api.auth import current_session_principal, require_permission
from backend.core.workspace_auth import (
    SESSION_COOKIE, SessionPrincipal, accept_workspace_invitation, authenticate_password,
    begin_totp_setup, disable_totp, enable_totp,
    create_workspace_invitation, disable_workspace_member, disable_workspace, get_workspace_lifecycle, public_registration_enabled,
    register_workspace_owner, revoke_session, session_public_profile, set_workspace_member_role,
    change_password, create_password_reset, consume_password_reset,
    create_email_verification, consume_email_verification,
    list_workspace_members, list_workspace_invitations, cancel_workspace_invitation,
    update_account_profile,
    enforce_auth_rate_limit, enforce_public_registration_rate_limit,
)
from backend.core.entitlements import EntitlementLimitExceeded, require_workspace_capacity

router = APIRouter(tags=["session"])


class SessionLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    totp_code: str | None = Field(default=None, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("A valid email is required")
        return value


class RegistrationRequest(SessionLoginRequest):
    display_name: str = Field(min_length=1, max_length=120)
    workspace_name: str = Field(min_length=1, max_length=120)


class InvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str


class InvitationAcceptanceRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=10, max_length=1024)
    display_name: str = Field(min_length=1, max_length=120)
    totp_code: str | None = Field(default=None, max_length=128)


class MemberRoleRequest(BaseModel):
    role: str


class TotpEnableRequest(BaseModel):
    setup_secret: str = Field(min_length=16, max_length=128)
    code: str = Field(min_length=6, max_length=8)


class PasswordConfirmation(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class PasswordChangeRequest(PasswordConfirmation):
    new_password: str = Field(min_length=10, max_length=1024)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordResetCompletion(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=10, max_length=1024)


class ProfileUpdateRequest(BaseModel):
    """Signed-in profile fields; workspace rename is Owner-only server-side."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_name: str | None = Field(default=None, min_length=1, max_length=120)


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class TotpDisableRequest(PasswordConfirmation):
    code: str = Field(min_length=6, max_length=128)


@router.post("/session/login")
async def login(body: SessionLoginRequest, response: Response, request: Request):
    try:
        await enforce_auth_rate_limit(
            "login", f"{request.client.host if request.client else 'unknown'}:{body.email}",
            limit=10, window_seconds=900,
        )
        token, principal = await authenticate_password(body.email, body.password, totp_code=body.totp_code)
        profile = await session_public_profile(principal)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=os.getenv("AITOB_SESSION_COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=int(os.getenv("AITOB_SESSION_TTL_HOURS", "12")) * 3600,
        path="/",
    )
    return profile


@router.post("/session/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegistrationRequest, response: Response, request: Request):
    """Implemented registration, explicitly closed until the isolation gate opens."""
    # Do not create a limiter row while registration is closed.  Once an
    # operator explicitly opens the gate, bound account creation by client
    # origin rather than email so changing email addresses cannot bypass it.
    if await public_registration_enabled():
        try:
            await enforce_public_registration_rate_limit(
                request.client.host if request.client else "unknown",
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many registration attempts. Try again later.",
            ) from exc
    try:
        principal = await register_workspace_owner(body.email, body.password, body.display_name, body.workspace_name)
        # Registration creates a session through the same durable session store.
        token, principal = await authenticate_password(body.email, body.password)
        profile = await session_public_profile(principal)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    response.set_cookie(key=SESSION_COOKIE, value=token, httponly=True,
                        secure=os.getenv("AITOB_SESSION_COOKIE_SECURE", "false").lower() == "true",
                        samesite="lax", max_age=int(os.getenv("AITOB_SESSION_TTL_HOURS", "12")) * 3600, path="/")
    return profile


@router.get("/session/registration-status")
async def registration_status():
    return {"enabled": await public_registration_enabled()}


@router.get("/session")
async def current_session(principal: SessionPrincipal = Depends(current_session_principal)):
    return await session_public_profile(principal)


@router.post("/session/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, principal: SessionPrincipal = Depends(current_session_principal)):
    if principal.session_id:
        await revoke_session(principal.session_id)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.post("/workspace/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(body: InvitationRequest, principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    try:
        await require_workspace_capacity(principal.workspace_id, "members")
        invite, token = await create_workspace_invitation(principal, body.email, body.role)
    except EntitlementLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    # The delivery service receives this one-time token later; the API returns
    # it only in this creation response and no server log/audit stores it.
    return {"invitation": invite, "acceptance_token": token}


@router.post("/workspace/invitations/accept")
async def accept_invitation(body: InvitationAcceptanceRequest, response: Response):
    try:
        await accept_workspace_invitation(body.token, body.password, body.display_name, totp_code=body.totp_code)
        # Look up via credential only after acceptance succeeded; no invitation
        # token or raw password is persisted by this route.
        # The invitation email is intentionally not projected before acceptance.
        # A user signs in normally after acceptance.
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"ok": True}


@router.put("/workspace/members/{user_id}/role")
async def update_member_role(user_id: str, body: MemberRoleRequest, principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    try:
        await set_workspace_member_role(principal, user_id, body.role)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/workspace/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(user_id: str, principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    try:
        await disable_workspace_member(principal, user_id)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/workspace/members")
async def members(principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    return {"members": await list_workspace_members(principal)}


@router.get("/workspace/invitations")
async def invitations(principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    """Return owner-visible invitation metadata without token material."""
    return {"invitations": await list_workspace_invitations(principal)}


@router.post("/workspace/disable", status_code=status.HTTP_202_ACCEPTED)
async def disable_current_workspace(principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    """Disable this workspace after all local/external work has drained.

    This is intentionally a reversible operational block rather than a hard
    delete; history and assets remain available for the retention/deletion
    workflow, while sessions are revoked immediately.
    """
    try:
        await disable_workspace(principal)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"disabled": True, "workspace_id": principal.workspace_id}


@router.get("/workspace/lifecycle")
async def workspace_lifecycle(principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    """Explain reversible disablement and the deliberately gated delete policy."""
    try:
        return await get_workspace_lifecycle(principal)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/workspace/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(invitation_id: str, principal: SessionPrincipal = Depends(require_permission("workspace.manage"))):
    try:
        await cancel_workspace_invitation(principal, invitation_id)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/session/password/change", status_code=204)
async def password_change(body: PasswordChangeRequest, principal: SessionPrincipal = Depends(current_session_principal)):
    try:
        await change_password(principal, body.password, body.new_password)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/session/profile")
async def profile_update(body: ProfileUpdateRequest, principal: SessionPrincipal = Depends(current_session_principal)):
    """Update account display name and, for Owners, the current workspace name."""
    try:
        return await update_account_profile(
            principal,
            display_name=body.display_name,
            workspace_name=body.workspace_name,
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/session/password/reset-request", status_code=202)
async def password_reset_request(body: PasswordResetRequest, request: Request):
    # Delivery is a deployment integration; never reveal whether an email exists.
    try:
        await enforce_auth_rate_limit(
            "password_reset", f"{request.client.host if request.client else 'unknown'}:{body.email}",
            limit=5, window_seconds=3600,
        )
        await create_password_reset(body.email)
    except PermissionError:
        # Enumeration-safe: a limited request has the same public response.
        pass
    return {"accepted": True, "delivery": "email_if_configured"}


@router.post("/session/password/reset", status_code=204)
async def password_reset(body: PasswordResetCompletion):
    try:
        await consume_password_reset(body.token, body.new_password)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/session/email-verification/request", status_code=202)
async def email_verification_request(principal: SessionPrincipal = Depends(current_session_principal)):
    await create_email_verification(principal)
    return {"accepted": True, "delivery": "email_if_configured"}


@router.post("/session/email-verification/confirm", status_code=204)
async def email_verification_confirm(body: TokenRequest):
    try:
        await consume_email_verification(body.token)
    except PermissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/session/mfa/setup")
async def mfa_setup(body: PasswordConfirmation, principal: SessionPrincipal = Depends(current_session_principal)):
    try:
        return {"setup_secret": await begin_totp_setup(principal, body.password)}
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/session/mfa/enable")
async def mfa_enable(body: TotpEnableRequest, principal: SessionPrincipal = Depends(current_session_principal)):
    try:
        recovery_codes = await enable_totp(principal, body.setup_secret, body.code)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    # Codes are returned exactly once and stored only as hashes.
    return {"enabled": True, "recovery_codes": recovery_codes}


@router.post("/session/mfa/disable")
async def mfa_disable(body: TotpDisableRequest, principal: SessionPrincipal = Depends(current_session_principal)):
    try:
        await disable_totp(principal, body.code, body.password)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"enabled": False}
