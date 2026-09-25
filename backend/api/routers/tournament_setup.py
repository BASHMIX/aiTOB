"""Resumable, workspace-scoped tournament setup draft endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, UploadFile, File

from backend.api.auth import require_permission
from backend.api.rollout import (
    require_provider_start_enabled,
    require_tournament_activation_enabled,
    require_tournament_setup_wizard_enabled,
)
from backend.api.schemas import (
    SetupDraftResponse, SetupDraftSectionPatch, ProviderScopeResolveRequest,
    ProviderScopeSelectRequest,
)
from backend.core.tournament_setup import (
    DraftError,
    DraftNotFound,
    DraftRevisionConflict,
    abandon_draft,
    create_draft,
    get_draft,
    list_drafts,
    patch_draft,
    reopen_draft_for_tournament,
)
from backend.core.workspace_auth import SessionPrincipal
from backend.core import integrations
from backend.core.provider_discovery import ProviderDiscoveryError, discover
from backend.core.tournament_setup import update_provider_scope
from backend.core.tournament_readiness import compute_readiness
from backend.core.tournament_operating_profile import validate_operating_profile
from backend.core.providers.startgg.wave_monitor import confirmation_patch
from backend.core.tournament_activation import ActivationError, materialize_draft, activate_tournament
from backend.core.provider_sync_manager import sync_manager
from backend.core import database
from backend.core.providers.registry import get_provider_for_tournament
from backend.api.routers.tournaments import provider_reference, serialize_tournament_for_frontend

router = APIRouter(
    tags=["tournament-setup"],
    dependencies=[Depends(require_tournament_setup_wizard_enabled)],
)


def _response(draft: dict) -> SetupDraftResponse:
    return SetupDraftResponse.model_validate(draft)


@router.post("/drafts", response_model=SetupDraftResponse, status_code=201)
async def create_setup_draft(principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    return _response(await create_draft(principal.workspace_id, principal.user_id))


@router.get("/drafts", response_model=list[SetupDraftResponse])
async def list_setup_drafts(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    statuses = {item.strip() for item in status.split(",")} if status else None
    return [_response(item) for item in await list_drafts(principal.workspace_id, statuses=statuses, limit=limit)]


@router.get("/drafts/{draft_id}", response_model=SetupDraftResponse)
async def read_setup_draft(draft_id: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    try:
        return _response(await get_draft(draft_id, principal.workspace_id))
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc


@router.post("/tournaments/{tournament_id:path}/edit", response_model=SetupDraftResponse)
async def edit_materialized_tournament_setup(
    tournament_id: str,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Reopen the wizard draft linked to an existing Hub tournament."""
    try:
        return _response(await reopen_draft_for_tournament(
            tournament_id, principal.workspace_id, principal.user_id,
        ))
    except DraftNotFound as exc:
        raise HTTPException(404, "This tournament was not created by the setup wizard or its setup draft is unavailable.") from exc


@router.patch("/drafts/{draft_id}", response_model=SetupDraftResponse)
async def patch_setup_draft(
    draft_id: str,
    body: SetupDraftSectionPatch,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    if if_match is None:
        raise HTTPException(428, "If-Match revision is required")
    try:
        expected_revision = int(if_match.strip('"'))
    except ValueError as exc:
        raise HTTPException(400, "If-Match must contain a draft revision") from exc
    try:
        draft = await patch_draft(
            draft_id,
            principal.workspace_id,
            principal.user_id,
            section=body.section,
            value=body.value,
            expected_revision=expected_revision,
            current_step=body.current_step,
        )
    except DraftRevisionConflict as exc:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": exc.latest}) from exc
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    except DraftError as exc:
        code = str(exc)
        status = 422 if code not in {"draft_not_editable"} else 409
        raise HTTPException(status, code) from exc
    response.headers["ETag"] = f'"{draft["revision"]}"'
    return _response(draft)


@router.delete("/drafts/{draft_id}", status_code=204)
async def delete_setup_draft(
    draft_id: str,
    if_match: str | None = Header(default=None, alias="If-Match"),
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    if if_match is None:
        raise HTTPException(428, "If-Match revision is required")
    try:
        await abandon_draft(draft_id, principal.workspace_id, expected_revision=int(if_match.strip('"')))
    except ValueError as exc:
        code = str(exc)
        status = 404 if code == "draft_not_found" else 409
        raise HTTPException(status, code) from exc
    return Response(status_code=204)


@router.post("/drafts/{draft_id}/provider-resolution", response_model=SetupDraftResponse)
async def resolve_provider_scope_for_draft(
    draft_id: str,
    body: ProviderScopeResolveRequest,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    try:
        draft = await get_draft(draft_id, principal.workspace_id)
        if int(draft["revision"]) != int(body.revision):
            raise DraftRevisionConflict(draft)
        account = await integrations.get_integration_account(
            body.provider_account_id, workspace_id=principal.workspace_id
        )
        if not account or account.get("provider_type") not in {"startgg", "challonge"}:
            raise HTTPException(404, "Provider connection not found")
        resolution = await discover(
            str(account["provider_type"]), body.provider_account_id, body.locator,
            challonge_subdomain=body.challonge_subdomain,
        )
        value = resolution.to_dict()
        updated = await patch_draft(
            draft_id, principal.workspace_id, principal.user_id,
            section="provider_scope", value=value, expected_revision=body.revision,
            current_step="provider",
        )
        return _response(updated)
    except HTTPException:
        raise
    except DraftRevisionConflict as exc:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": exc.latest}) from exc
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    except ProviderDiscoveryError as exc:
        raise HTTPException(exc.status_code, exc.to_dict()) from exc
    except DraftError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/drafts/{draft_id}/provider-scope", response_model=SetupDraftResponse)
async def select_provider_scope_for_draft(
    draft_id: str,
    body: ProviderScopeSelectRequest,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    try:
        draft = await get_draft(draft_id, principal.workspace_id)
        if int(draft["revision"]) != int(body.revision):
            raise DraftRevisionConflict(draft)
        answer = draft.get("provider_scope") or {}
        scopes = answer.get("scopes") if isinstance(answer, dict) else []
        selected = next((scope for scope in scopes if str(scope.get("external_id")) == body.external_scope_id), None)
        if not selected:
            raise DraftError("provider_scope_not_in_latest_resolution")
        updated = await update_provider_scope(
            draft_id, principal.workspace_id, principal.user_id,
            expected_revision=body.revision,
            provider_account_id=str(answer.get("account_id") or answer.get("provider_account_id") or ""),
            provider_type=str(answer.get("provider") or answer.get("provider_type") or ""),
            external_tournament_id=str((answer.get("tournament") or {}).get("external_id") or ""),
            external_scope_id=body.external_scope_id,
            external_tournament_slug=(answer.get("tournament") or {}).get("canonical_slug"),
            external_scope_slug=selected.get("canonical_slug"),
            provider_observed_at=answer.get("observed_at"),
        )
        new_answer = dict(answer)
        new_answer["selected_scope"] = selected
        new_answer["resolution"] = "selected_scope"
        # Keep the safe full preview in the draft while columns remain the
        # authoritative binding fields used by activation.
        return _response(await patch_draft(
            draft_id, principal.workspace_id, principal.user_id,
            section="provider_scope", value=new_answer,
            expected_revision=int(updated["revision"]), current_step="provider",
        ))
    except DraftRevisionConflict as exc:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": exc.latest}) from exc
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    except DraftError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/drafts/{draft_id}/readiness")
async def setup_readiness(
    draft_id: str,
    body: dict[str, object] | None = None,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    try:
        draft = await get_draft(draft_id, principal.workspace_id)
        if body and body.get("revision") is not None and int(body["revision"]) != int(draft["revision"]):
            raise DraftRevisionConflict(draft)
        return await compute_readiness(draft_id, principal.workspace_id, purpose=str((body or {}).get("purpose") or "draft_review"))
    except DraftRevisionConflict as exc:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": exc.latest}) from exc
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc


@router.post(
    "/drafts/{draft_id}/provider-start",
    dependencies=[Depends(require_provider_start_enabled)],
)
async def guarded_provider_start(
    draft_id: str,
    body: dict[str, object] | None = None,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    try:
        draft = await get_draft(draft_id, principal.workspace_id)
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    if body and body.get("revision") is not None and int(body["revision"]) != int(draft["revision"]):
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": draft})
    provider = str((draft.get("provider_scope") or {}).get("provider") or "")
    if provider == "startgg":
        from backend.core.providers.startgg.remote_start import StartGGRemoteStart
        result = await StartGGRemoteStart().preflight()
    elif provider == "challonge":
        from backend.core.providers.challonge.remote_start import ChallongeRemoteStart
        result = await ChallongeRemoteStart().preflight()
    else:
        raise HTTPException(409, {"code": "provider_scope_required", "message": "Select a provider scope before starting.", "retryable": False})
    raise HTTPException(409, {"code": result.reason_code, "message": result.message, "retryable": False})


async def _patch_section(draft_id: str, section: str, body: dict[str, object], principal: SessionPrincipal):
    revision = body.get("revision")
    if revision is None:
        raise HTTPException(428, "revision is required")
    value = body.get("value")
    if not isinstance(value, dict):
        value = {key: item for key, item in body.items() if key not in {"revision", "value"}}
    if section == "operating_profile":
        try:
            value = validate_operating_profile(value).as_dict()
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
    try:
        return _response(await patch_draft(draft_id, principal.workspace_id, principal.user_id, section=section, value=value, expected_revision=int(revision), current_step="tournament" if section in {"tournament_review", "operating_profile"} else "discord"))
    except DraftRevisionConflict as exc:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": exc.latest}) from exc
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    except DraftError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/drafts/{draft_id}/tournament-review", response_model=SetupDraftResponse)
async def patch_tournament_review(draft_id: str, body: dict[str, object], principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    return await _patch_section(draft_id, "tournament_review", body, principal)


@router.put("/drafts/{draft_id}/operating-profile", response_model=SetupDraftResponse)
async def patch_operating_profile(draft_id: str, body: dict[str, object], principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    return await _patch_section(draft_id, "operating_profile", body, principal)


@router.post("/drafts/{draft_id}/wave-confirmation", response_model=SetupDraftResponse)
async def confirm_wave_monitoring(draft_id: str, body: dict[str, object], principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    revision = body.get("revision")
    if revision is None:
        raise HTTPException(428, "revision is required")
    confirmed = bool(body.get("confirmed", True))
    value = {"organizer_confirmation": confirmation_patch(confirmed=confirmed, actor_id=principal.user_id)}
    return await _patch_section(draft_id, "operating_profile", {"revision": revision, "value": value}, principal)


@router.post(
    "/drafts/{draft_id}/materialize",
    dependencies=[Depends(require_tournament_activation_enabled)],
)
async def materialize_setup_draft(draft_id: str, body: dict[str, object], principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    try:
        materialized = await materialize_draft(
            draft_id,
            principal.workspace_id,
            principal.user_id,
            expected_revision=int(body.get("revision") or 0),
        )
        # Adding a tournament to the Hub must not start its provider bracket,
        # but it should populate the local read-only projection immediately.
        # A provider outage/token problem must not undo the saved wizard draft;
        # the card remains available for a later manual Sync.
        try:
            tournament = await database.get_tournament(
                str(materialized["tournament_id"]), principal.workspace_id
            )
            if tournament:
                # Materialization stores only the redacted wizard preview so
                # provider discovery remains a read-only boundary.  Populate
                # the durable frontend projection now that the tournament is
                # saved, otherwise the Hub's Tournament Data panel has events
                # but no ``events[].entrants`` to render.  A metadata outage
                # must not prevent the bracket snapshot from being synced.
                try:
                    provider = await get_provider_for_tournament(
                        str(materialized["tournament_id"]), principal.workspace_id
                    )
                    info = await provider.fetch_tournament(provider_reference(tournament))
                    if info:
                        await database.update_tournament_settings(
                            str(materialized["tournament_id"]),
                            principal.workspace_id,
                            raw_data=json.dumps(serialize_tournament_for_frontend(info), ensure_ascii=False),
                        )
                except Exception:
                    # Keep the card and continue with the bracket sync; the
                    # Hub's Refresh Metadata action can retry this read later.
                    pass
                if tournament.get("provider_type") == "startgg":
                    # A wizard-created card should retain its seeded matches
                    # while the provider bracket is waiting to be started.
                    await database.update_tournament_settings(
                        str(materialized["tournament_id"]),
                        principal.workspace_id,
                        ignore_activity_guard=True,
                    )
                await sync_manager.sync_bracket(
                    str(materialized["tournament_id"]),
                    workspace_id=principal.workspace_id,
                    reason="setup",
                    ignore_activity_guard=tournament.get("provider_type") == "startgg",
                )
                materialized["initial_sync"] = "completed"
            else:
                materialized["initial_sync"] = "skipped"
        except Exception:
            materialized["initial_sync"] = "failed"
        return materialized
    except DraftRevisionConflict as exc:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": exc.latest}) from exc
    except ActivationError as exc:
        code = str(exc)
        detail: dict[str, object] = {"code": code, "retryable": False}
        if code == "readiness_blocked":
            readiness = await compute_readiness(draft_id, principal.workspace_id, purpose="materialize")
            blocked = next((check for check in readiness["checks"] if check["state"] == "blocked"), None)
            detail.update({"message": blocked["message"] if blocked else "Complete the required setup checks before saving the tournament.", "readiness": readiness})
        raise HTTPException(409 if code == "readiness_blocked" else 404, detail) from exc
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc


@router.post(
    "/tournaments/{tournament_id}/activate",
    dependencies=[Depends(require_tournament_activation_enabled)],
)
async def activate_setup_tournament(tournament_id: str, body: dict[str, object] | None = None, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    try:
        return await activate_tournament(principal.workspace_id, tournament_id, principal.user_id, idempotency_key=str((body or {}).get("idempotency_key") or "1"))
    except ActivationError as exc:
        raise HTTPException(404 if str(exc) == "tournament_not_found" else 409, {"code": str(exc), "retryable": False}) from exc


@router.post(
    "/drafts/{draft_id}/activate",
    dependencies=[Depends(require_tournament_activation_enabled)],
)
async def activate_setup_draft(draft_id: str, body: dict[str, object], principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    try:
        materialized = await materialize_draft(draft_id, principal.workspace_id, principal.user_id, expected_revision=int(body.get("revision") or 0))
        return await activate_tournament(principal.workspace_id, str(materialized["tournament_id"]), principal.user_id, idempotency_key=str(body.get("idempotency_key") or "1"))
    except DraftRevisionConflict as exc:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": exc.latest}) from exc
    except (ActivationError, DraftNotFound) as exc:
        code = str(exc)
        detail: dict[str, object] = {"code": code, "retryable": False}
        if code == "readiness_blocked":
            readiness = await compute_readiness(draft_id, principal.workspace_id, purpose="materialize")
            blocked = next((check for check in readiness["checks"] if check["state"] == "blocked"), None)
            detail.update({"message": blocked["message"] if blocked else "Complete the required setup checks before activation.", "readiness": readiness})
        raise HTTPException(409 if code == "readiness_blocked" else 404, detail) from exc


@router.post("/drafts/{draft_id}/logo")
async def upload_draft_logo(draft_id: str, file: UploadFile = File(...), revision: int = Query(...), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    try:
        draft = await get_draft(draft_id, principal.workspace_id)
    except DraftNotFound as exc:
        raise HTTPException(404, "Draft not found") from exc
    if int(draft["revision"]) != int(revision):
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": draft})
    content = await file.read(5 * 1024 * 1024 + 1)
    from backend.core.player_image_service import validate_player_image
    checked = validate_player_image(content, mime_type=file.content_type)
    if not checked.ok or not checked.normalized_bytes:
        raise HTTPException(422, {"code": checked.reason_code, "retryable": False})
    from backend.core.database import record_media_asset
    import uuid
    asset = await record_media_asset(workspace_id=principal.workspace_id, asset_type="tournament_logo", owner_type="tournament_setup_draft", owner_id=draft_id, storage_url=f"data:image/png;base64,{__import__('base64').b64encode(checked.normalized_bytes).decode('ascii')}", mime_type="image/png", byte_size=len(checked.normalized_bytes), width=checked.width, height=checked.height)
    updated = await patch_draft(draft_id, principal.workspace_id, principal.user_id, section="tournament_review", value={**draft.get("tournament_review", {}), "logo_asset_id": asset["id"]}, expected_revision=revision, current_step="tournament")
    return {"asset": {"id": asset["id"], "url": asset["storage_url"]}, "draft": updated}


@router.delete("/drafts/{draft_id}/logo")
async def delete_draft_logo(draft_id: str, if_match: str | None = Header(default=None, alias="If-Match"), principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    if if_match is None:
        raise HTTPException(428, "If-Match revision is required")
    draft = await get_draft(draft_id, principal.workspace_id)
    revision = int(if_match.strip('"'))
    if int(draft["revision"]) != revision:
        raise HTTPException(409, {"code": "draft_version_conflict", "latest_draft": draft})
    logo_id = (draft.get("tournament_review") or {}).get("logo_asset_id")
    if logo_id:
        from backend.core.database import delete_media_asset
        await delete_media_asset(str(logo_id), principal.workspace_id)
    return _response(await patch_draft(draft_id, principal.workspace_id, principal.user_id, section="tournament_review", value={**draft.get("tournament_review", {}), "logo_asset_id": None}, expected_revision=revision, current_step="tournament"))
