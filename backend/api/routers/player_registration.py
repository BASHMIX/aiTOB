"""Workspace and tournament-scoped player registration APIs."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, Query

from backend.api.auth import require_permission
from backend.api.schemas import ManualDiscordLinkRequest, RegistrationConfigRequest, RegistrationStateActionRequest
from backend.core import database
from backend.core.player_registration import (
    RegistrationError, get_enrollment, get_registration_config, list_enrollments,
    link_discord_member, registration_window_state, set_registration_status,
    transition_enrollment, unlink_discord_member, upsert_registration_config,
)
from backend.core.registration_sync import recheck_provider_roster
from backend.core.workspace_auth import SessionPrincipal

router = APIRouter(tags=["player-registration"])


def _require_idempotency(key: str | None) -> str:
    value = str(key or "").strip()
    if not value or len(value) > 200:
        raise HTTPException(status_code=428, detail="idempotency_key_required")
    return value


async def _tournament(tournament_id: str, workspace_id: str) -> dict[str, Any]:
    row = await database.get_tournament(tournament_id, workspace_id)
    if not row:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return row


async def _binding(tournament_id: str, workspace_id: str, table: str) -> dict[str, Any] | None:
    if table not in {"tournament_discord_bindings", "provider_scope_bindings"}:
        raise ValueError("unsupported binding table")
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = database.aiosqlite.Row
        row = await (await db.execute(
            f"SELECT * FROM {table} WHERE tournament_id=? AND workspace_id=?",
            (tournament_id, workspace_id),
        )).fetchone()
    return dict(row) if row else None


async def _audit(principal: SessionPrincipal, action: str, target_id: str, detail: dict[str, Any] | None = None) -> None:
    try:
        await database.record_audit_event(
            workspace_id=principal.workspace_id, actor_id=principal.user_id,
            action=action, outcome="accepted", target_type="tournament_registration",
            target_id=target_id, detail=detail or {},
        )
    except Exception:
        pass


def _response(config: dict[str, Any] | None) -> dict[str, Any]:
    if not config:
        return {
            "enabled": False, "destination_external_id": None,
            "opens_at": None, "closes_at": None, "display_timezone": "UTC",
            "require_provider_registration": True,
            "gamertag_verification_policy": "match_or_set_nickname",
            "startgg_bio_verification_enabled": False, "image_policy": "optional",
            "verified_role_external_id": None, "announcement_policy": {},
            "schedule_version": 1, "status": "disabled",
        }
    value = dict(config)
    computed = registration_window_state(config)
    stored = str(config.get("status") or "")
    # Explicit organizer close is sticky, while an explicit open may still be
    # superseded by the server-enforced closing instant. Scheduled rows follow
    # the current server clock so the UI never trusts a stale browser timer.
    if stored == "disabled":
        value["status"] = "disabled"
    elif stored == "closed":
        value["status"] = "closed"
    elif stored == "open" and computed != "closed":
        value["status"] = "open"
    else:
        value["status"] = computed
    return value


@router.get("/tournaments/{tournament_id}/registration/config")
async def read_registration_config(tournament_id: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    await _tournament(tournament_id, principal.workspace_id)
    return _response(await get_registration_config(tournament_id, principal.workspace_id))


@router.put("/tournaments/{tournament_id}/registration/config")
async def write_registration_config(tournament_id: str, body: RegistrationConfigRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    tournament = await _tournament(tournament_id, principal.workspace_id)
    provider_type = str(tournament.get("provider_type") or "").lower()
    if body.startgg_bio_verification_enabled and provider_type not in {"", "startgg"}:
        raise HTTPException(status_code=422, detail="startgg_bio_unavailable_for_provider")
    try:
        value = await upsert_registration_config(tournament_id, principal.workspace_id, principal.user_id, body.model_dump(exclude_none=True))
    except RegistrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await _audit(principal, "registration.config.updated", tournament_id, {"enabled": body.enabled})
    return _response(value)


@router.get("/tournaments/{tournament_id}/registrations")
async def read_registrations(tournament_id: str, state: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=500), principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    await _tournament(tournament_id, principal.workspace_id)
    try:
        rows = await list_enrollments(tournament_id, principal.workspace_id, state=state, limit=limit)
    except RegistrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("state") or "needs_review")
        counts[key] = counts.get(key, 0) + 1
    return {"registrations": rows, "enrollments": rows, "counts": counts, "next_cursor": None}


@router.put("/tournaments/{tournament_id}/registrations/{enrollment_id}/discord-link")
async def add_manual_discord_link(tournament_id: str, enrollment_id: str, body: ManualDiscordLinkRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    await _tournament(tournament_id, principal.workspace_id)
    binding = await _binding(tournament_id, principal.workspace_id, "tournament_discord_bindings")
    if not binding or not binding.get("guild_id"):
        raise HTTPException(status_code=409, detail="discord_binding_required")
    try:
        result = await link_discord_member(
            enrollment_id, tournament_id, principal.workspace_id, body.discord_user_id,
            actor_id=principal.user_id, guild_id=str(binding["guild_id"]),
        )
    except RegistrationError as exc:
        code = str(exc)
        code_status = 404 if code == "enrollment_not_found" else 409 if code in {"discord_user_already_linked", "discord_member_not_in_guild"} else 422
        raise HTTPException(status_code=code_status, detail=code) from exc
    await _audit(principal, "registration.discord_link.updated", enrollment_id, {"guild_id": str(binding["guild_id"])})
    return result


@router.delete("/tournaments/{tournament_id}/registrations/{enrollment_id}/discord-link")
async def remove_manual_discord_link(tournament_id: str, enrollment_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    await _tournament(tournament_id, principal.workspace_id)
    try:
        result = await unlink_discord_member(enrollment_id, tournament_id, principal.workspace_id, actor_id=principal.user_id)
    except RegistrationError as exc:
        raise HTTPException(status_code=404 if str(exc) == "enrollment_not_found" else 422, detail=str(exc)) from exc
    await _audit(principal, "registration.discord_link.removed", enrollment_id)
    return result


async def _transition_action(tournament_id: str, enrollment_id: str, principal: SessionPrincipal, *, state: str, reason: str | None):
    await _tournament(tournament_id, principal.workspace_id)
    try:
        result = await transition_enrollment(enrollment_id, tournament_id, principal.workspace_id, state, reason_code=reason, actor_id=principal.user_id)
    except RegistrationError as exc:
        raise HTTPException(status_code=404 if str(exc) == "enrollment_not_found" else 422, detail=str(exc)) from exc
    await _audit(principal, f"registration.enrollment.{state}", enrollment_id, {"reason": reason} if reason else None)
    return result


@router.post("/tournaments/{tournament_id}/registrations/{enrollment_id}/approve-link")
async def approve_registration_link(tournament_id: str, enrollment_id: str, body: RegistrationStateActionRequest | None = None, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    enrollment = await get_enrollment(enrollment_id, tournament_id, principal.workspace_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="enrollment_not_found")
    if not enrollment.get("discord_user_id") or not enrollment.get("provider_entrant_id"):
        raise HTTPException(status_code=409, detail="provider_and_discord_link_required")
    return await _transition_action(tournament_id, enrollment_id, principal, state="ready", reason=(body.reason if body else "organizer_approved"))


@router.post("/tournaments/{tournament_id}/registrations/{enrollment_id}/request-image")
async def request_registration_image(tournament_id: str, enrollment_id: str, body: RegistrationStateActionRequest | None = None, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    return await _transition_action(tournament_id, enrollment_id, principal, state="awaiting_image", reason=(body.reason if body else "image_required"))


@router.post("/tournaments/{tournament_id}/registrations/{enrollment_id}/reject")
async def reject_registration(tournament_id: str, enrollment_id: str, body: RegistrationStateActionRequest | None = None, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    return await _transition_action(tournament_id, enrollment_id, principal, state="rejected", reason=(body.reason if body else "organizer_rejected"))


@router.post("/tournaments/{tournament_id}/registration/open")
async def open_registration(tournament_id: str, body: RegistrationStateActionRequest | None = None, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    await _tournament(tournament_id, principal.workspace_id)
    config = await get_registration_config(tournament_id, principal.workspace_id)
    if not config or not config.get("enabled"):
        raise HTTPException(status_code=409, detail="registration_disabled")
    try:
        result = await set_registration_status(tournament_id, principal.workspace_id, "open", actor_id=principal.user_id, reason=body.reason if body else None)
        from backend.core.workflow_outbox import build_registration_job_event
        await database.enqueue_workflow_outbox_v2(build_registration_job_event(workspace_id=principal.workspace_id, tournament_id=tournament_id, operation="open", schedule_version=result["schedule_version"], payload={"idempotency_key": idempotency_key.strip()}))
    except RegistrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _audit(principal, "registration.window.open", tournament_id, {"schedule_version": result["schedule_version"]})
    return _response(result)


@router.post("/tournaments/{tournament_id}/registration/close")
async def close_registration(tournament_id: str, body: RegistrationStateActionRequest | None = None, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    await _tournament(tournament_id, principal.workspace_id)
    if not await get_registration_config(tournament_id, principal.workspace_id):
        raise HTTPException(status_code=404, detail="registration_config_not_found")
    try:
        result = await set_registration_status(tournament_id, principal.workspace_id, "closed", actor_id=principal.user_id, reason=body.reason if body else None)
        from backend.core.workflow_outbox import build_registration_job_event
        await database.enqueue_workflow_outbox_v2(build_registration_job_event(workspace_id=principal.workspace_id, tournament_id=tournament_id, operation="close", schedule_version=result["schedule_version"], payload={"idempotency_key": idempotency_key.strip()}))
    except RegistrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _audit(principal, "registration.window.close", tournament_id, {"schedule_version": result["schedule_version"]})
    return _response(result)


@router.post("/tournaments/{tournament_id}/registration/recheck")
async def recheck_registration(tournament_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    _require_idempotency(idempotency_key)
    tournament = await _tournament(tournament_id, principal.workspace_id)
    binding = await _binding(tournament_id, principal.workspace_id, "provider_scope_bindings")
    provider_type = str((binding or {}).get("provider_type") or tournament.get("provider_type") or "").lower()
    provider_account_id = str((binding or {}).get("provider_account_id") or tournament.get("provider_account_id") or "")
    external_scope_id = str((binding or {}).get("external_scope_id") or tournament.get("event_id") or tournament.get("provider_tournament_id") or "")
    provider_tournament_id = str((binding or {}).get("external_tournament_id") or tournament.get("provider_tournament_id") or tournament.get("slug") or "")
    if not provider_type or not provider_account_id or not external_scope_id or not provider_tournament_id:
        raise HTTPException(status_code=409, detail="provider_scope_binding_required")
    try:
        from backend.core.providers.registry import get_provider_for_tournament
        provider = await get_provider_for_tournament(tournament_id, principal.workspace_id)
        result = await recheck_provider_roster(tournament_id, principal.workspace_id, provider_type=provider_type, provider_account_id=provider_account_id, external_scope_id=external_scope_id, provider_tournament_id=provider_tournament_id, provider=provider)
    except RegistrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="provider_recheck_unavailable") from exc
    await _audit(principal, "registration.roster.recheck", tournament_id, {"external_scope_id": external_scope_id, "status": result.status})
    return result.to_dict()


__all__ = ["router"]
