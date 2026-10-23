"""API Router for Tournament Results Media."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.auth import current_session_principal, require_permission
from backend.api.results_media_schemas import (
    CreateMediaOutputRequest,
    ExportReceiptRequest,
    ExportReceiptResponse,
    MediaOutputResponse,
    PageInfo,
    ReadinessWarning,
    RefreshFailure,
    RefreshRequest,
    RefreshResult,
    ResultVersionResponse,
    StandingEntry,
)
from backend.core import database
from backend.core import results_media
from backend.core import results_media_repository as repo
from backend.core.workspace_auth import SessionPrincipal, enforce_auth_rate_limit, permission_allowed

router = APIRouter(tags=["results-media"])


def _format_version_response(version: dict[str, Any], entries: list[dict[str, Any]], page_meta: dict[str, Any] | None = None) -> ResultVersionResponse:
    warnings = []
    for w in (version.get("warnings") or version.get("warning_json") or []):
        if isinstance(w, str):
            warnings.append(ReadinessWarning(code="warning", severity="warning", message=w))
        elif isinstance(w, dict):
            warnings.append(ReadinessWarning(
                code=w.get("code", "warning"),
                severity=w.get("severity", "warning"),
                entrant_id=w.get("entrant_id"),
                message=w.get("message", ""),
            ))

    entry_models = []
    for e in entries:
        pres = e.get("presentation") or {}
        entry_models.append(StandingEntry(
            ordinal=e["ordinal"],
            placement=e["placement"],
            entrant_id=e["entrant_id"],
            entrant_name=e["entrant_name"],
            provider_user_id=e.get("provider_user_id"),
            player_profile_id=e.get("player_profile_id"),
            is_tied=e.get("is_tied", False),
            presentation=pres,
        ))

    p_info = None
    if page_meta:
        p_info = PageInfo(
            number=page_meta.get("number", 1),
            size=page_meta.get("size", 16),
            total_entries=page_meta.get("total_entries", len(entry_models)),
            has_more=page_meta.get("has_more", False),
        )

    readiness = results_media.result_version_readiness(version)
    return ResultVersionResponse(
        id=str(version["id"]),
        tournament_slug=version["tournament_slug"],
        provider_type=version["provider_type"],
        event_id=version["event_id"],
        event_name=version["event_name"],
        game_id=version.get("game_id"),
        game_name=version.get("game_name"),
        capture_status=version["capture_status"],
        readiness_state=readiness,
        provider_state_raw=version["provider_state_raw"],
        provider_revision=version.get("provider_revision"),
        observed_at=str(version["observed_at"]),
        finalized_at=str(version["finalized_at"]) if version.get("finalized_at") else None,
        entry_count=version.get("entry_count", len(entry_models)),
        warnings=warnings,
        page=p_info,
        entries=entry_models,
    )


@router.get(
    "/api/tournaments/{tournament_slug}/events/{event_id}/results/latest",
    response_model=ResultVersionResponse,
    summary="Read latest result version for an event without provider I/O",
)
async def get_latest_event_results(
    tournament_slug: str,
    event_id: str,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    tournament = await database.get_tournament(tournament_slug, principal.workspace_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    latest = await repo.get_latest_result_version(principal.workspace_id, tournament_slug, event_id)
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No result version found for event")

    entries, page_meta = await repo.get_version_entries(principal.workspace_id, latest["id"], cutoff="top8", page=1, page_size=512)
    return _format_version_response(latest, entries, page_meta)


@router.post(
    "/api/tournaments/{tournament_slug}/events/{event_id}/results/refresh",
    response_model=RefreshResult,
    summary="Fetch provider standings and create or reuse an immutable result version",
)
async def refresh_event_results_endpoint(
    tournament_slug: str,
    event_id: str,
    body: RefreshRequest,
    principal: SessionPrincipal = Depends(require_permission("results.manage")),
):
    tournament = await database.get_tournament(tournament_slug, principal.workspace_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    try:
        await enforce_auth_rate_limit(
            "results_refresh",
            f"{principal.workspace_id}:{tournament_slug}:{event_id}",
            limit=20,
            window_seconds=60,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh requests. Try again in a minute.",
        ) from exc

    try:
        res = await results_media.refresh_event_results(
            workspace_id=principal.workspace_id,
            tournament_slug=tournament_slug,
            event_id=event_id,
            user_id=principal.user_id,
            force=body.force,
            presentation_mode=body.presentation_mode,
        )
    except ValueError as exc:
        await database.record_audit_event(
            workspace_id=principal.workspace_id,
            actor_id=principal.user_id,
            action="results.refresh",
            outcome="failure",
            target_type="tournament_event",
            target_id=f"{tournament_slug}:{event_id}",
            detail={"error_type": "validation", "message": str(exc)[:500]},
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except TimeoutError:
        await database.record_audit_event(
            workspace_id=principal.workspace_id,
            actor_id=principal.user_id,
            action="results.refresh",
            outcome="failure",
            target_type="tournament_event",
            target_id=f"{tournament_slug}:{event_id}",
            detail={"error_type": "timeout"},
        )
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Provider request timed out")
    except Exception as exc:
        await database.record_audit_event(
            workspace_id=principal.workspace_id,
            actor_id=principal.user_id,
            action="results.refresh",
            outcome="failure",
            target_type="tournament_event",
            target_id=f"{tournament_slug}:{event_id}",
            detail={"error_type": type(exc).__name__, "message": "Provider results refresh failed"},
        )
        # The redacted diagnostic is retained in the audit trail.  API clients
        # receive a stable message so unknown provider/library exceptions can
        # never become an accidental credential or payload disclosure.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provider results refresh failed",
        )

    version = res["version"]
    entries, page_meta = await repo.get_version_entries(principal.workspace_id, version["id"], cutoff="top8", page=1, page_size=512)
    resp_version = _format_version_response(version, entries, page_meta)
    return RefreshResult(
        version=resp_version,
        reused=res["reused"],
        readiness_state=res["readiness_state"],
    )


@router.get(
    "/api/results-media/versions/{version_id}",
    response_model=ResultVersionResponse,
    summary="Read one immutable result version and its paged entries",
)
async def get_version_by_id(
    version_id: str,
    cutoff: Literal["top8", "top16", "all"] = Query("top8"),
    page: int = Query(1, ge=1),
    page_size: int = Query(16, ge=1, le=512),
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    version = await repo.get_result_version_by_id(principal.workspace_id, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result version not found")

    entries, page_meta = await repo.get_version_entries(principal.workspace_id, version_id, cutoff=cutoff, page=page, page_size=page_size)
    return _format_version_response(version, entries, page_meta)


@router.post(
    "/api/results-media/versions/{version_id}/outputs",
    response_model=MediaOutputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Freeze a normalized scene and result binding for static or live use",
)
async def create_media_output_endpoint(
    version_id: str,
    body: CreateMediaOutputRequest,
    principal: SessionPrincipal = Depends(current_session_principal),
):
    if body.output_kind == "static" and not permission_allowed(principal.role, "results.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="results.manage required for static export")
    if body.output_kind == "live" and not permission_allowed(principal.role, "results.broadcast"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="results.broadcast required for live overlay")

    version = await repo.get_result_version_by_id(principal.workspace_id, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result version not found")

    readiness = results_media.result_version_readiness(version)
    if readiness != "final":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {readiness} result version cannot be published as a frozen output",
        )

    scene_errors = results_media.validate_results_scene(
        body.scene,
        version_id=version_id,
        require_sequence=body.output_kind == "live",
    )
    canvas = body.scene.get("canvas") if isinstance(body.scene, dict) else None
    if isinstance(canvas, dict) and all(
        isinstance(canvas.get(key), (int, float)) for key in ("width", "height")
    ) and (
        int(canvas["width"]) != body.output_profile.width
        or int(canvas["height"]) != body.output_profile.height
    ):
        scene_errors.append("scene_canvas_must_match_output_profile")
    if isinstance(body.scene, dict):
        for node in (body.scene.get("nodes") or {}).values():
            if not isinstance(node, dict) or node.get("type") != "results-group":
                continue
            if node.get("cutoff") != body.cutoff:
                scene_errors.append("scene_cutoff_must_match_output")
            # The selected output page is stored on the immutable output row.
            # Its frozen scene receives only that page's entries and must not
            # apply the same offset a second time in the browser renderer.
            if node.get("pageNumber") != 1:
                scene_errors.append("scene_page_number_must_be_1_for_frozen_output")
    if scene_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_results_scene", "errors": list(dict.fromkeys(scene_errors))},
        )

    entries, page_meta = await repo.get_version_entries(
        principal.workspace_id,
        version_id,
        cutoff=body.cutoff,
        page=body.page_number,
        page_size=results_media.results_scene_page_size(body.scene),
    )
    if not entries:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected results page is empty")

    scene_hash = hashlib.sha256(
        json.dumps(body.scene, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    output = await repo.create_media_output(
        workspace_id=principal.workspace_id,
        output_data={
            "result_version_id": version_id,
            "output_kind": body.output_kind,
            "overlay_name": body.overlay_name,
            "scene_schema_version": 2,
            "scene_config": body.scene,
            "scene_hash": scene_hash,
            "cutoff": body.cutoff,
            "page_number": body.page_number,
            "output_profile": body.output_profile.model_dump(),
            "created_by": principal.user_id,
        },
    )
    await database.record_audit_event(
        workspace_id=principal.workspace_id,
        actor_id=principal.user_id,
        action="results.output.create",
        outcome="success",
        target_type="results_media_output",
        target_id=output["id"],
        detail={
            "result_version_id": version_id,
            "output_kind": body.output_kind,
            "cutoff": body.cutoff,
            "page_number": body.page_number,
            "entry_count": len(entries),
            "page_total": page_meta["total_entries"],
        },
    )
    return MediaOutputResponse(
        id=output["id"],
        result_version_id=output["result_version_id"],
        output_kind=output["output_kind"],
        scene_hash=output["scene_hash"],
        cutoff=output["cutoff"],
        page_number=output["page_number"],
        output_profile=output["output_profile"],
        created_at=str(output["created_at"]),
    )


@router.post(
    "/api/results-media/outputs/{output_id}/export-receipt",
    response_model=ExportReceiptResponse,
    summary="Record a successful client-side PNG rasterization before download",
)
async def record_export_receipt_endpoint(
    output_id: str,
    body: ExportReceiptRequest,
    principal: SessionPrincipal = Depends(require_permission("results.manage")),
):
    try:
        await enforce_auth_rate_limit(
            "export_receipt",
            f"{principal.workspace_id}:{output_id}",
            limit=60,
            window_seconds=60,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many export receipts recorded.",
        ) from exc

    output = await repo.get_media_output(principal.workspace_id, output_id)
    if not output:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media output not found")

    if output["output_kind"] != "static":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export receipts apply only to static outputs")

    receipt_status = await repo.record_export_receipt(
        workspace_id=principal.workspace_id,
        output_id=output_id,
        byte_size=body.byte_size,
        sha256=body.sha256,
    )
    if receipt_status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media output not found")
    if receipt_status == "conflict":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export receipt does not match the existing immutable receipt")

    await database.record_audit_event(
        workspace_id=principal.workspace_id,
        actor_id=principal.user_id,
        action="results.export.receipt",
        outcome="success",
        target_type="results_media_output",
        target_id=output_id,
        detail={
            "byte_size": body.byte_size,
            "sha256": body.sha256,
            "idempotent": receipt_status == "unchanged",
        },
    )

    return ExportReceiptResponse(output_id=output_id, recorded=True)
