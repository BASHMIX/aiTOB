from fastapi import APIRouter, Request, HTTPException, Depends, status
import json
from datetime import UTC, datetime
from typing import Dict, Any, List, Optional
from backend.core.database import (
    upsert_tournament, get_tournaments, get_tournament, delete_tournament, TournamentRemovalBlocked,
    update_tournament_settings, delete_tournament_active_matches, sync_active_matches,
    get_all_player_overrides, set_tournament_streams, get_tournament_streams,
    get_stations, set_tournament_sync_status, get_bracket_snapshot,
    get_live_sync_state_v2, get_setting, cancel_pending_dispatcher_work,
)
from backend.core.providers.registry import get_provider, get_provider_for_tournament
from backend.core.contracts.tournament_types import ProviderSet, ProviderTournament
from backend.core.provider_sync_manager import sync_manager
from backend.core.provider_projection import tournament_provider_projection
from backend.core.challonge_resolution import resolution_service
from backend.core.provider_feature_flags import get_provider_feature_flags
from backend.core.providers.challonge.client import ChallongeError, ChallongeRateLimitError
from backend.core.database import persist_challonge_identity
from backend.core.entitlements import EntitlementLimitExceeded, require_workspace_capacity
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password, require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import (
    AddTournamentRequest, PatchTournamentSettingsRequest, MessageResponse, ErrorResponse, TournamentsResponse,
    ProviderCapabilityProfileResponse,
    ChallongeStateRepairDryRunRequest,
)

router = APIRouter(tags=["tournaments"])


def _workspace(principal: SessionPrincipal | object) -> str | None:
    """FastlóAPI always supplies a principal; direct legacy unit calls do not."""
    return getattr(principal, "workspace_id", None)


def _dispatcher_service_alive(value: str | None) -> bool:
    """A heartbeat is advisory only; it never arms or starts the Dispatcher."""
    if not value:
        return False
    try:
        seen = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=UTC)
        return (datetime.now(UTC) - seen.astimezone(UTC)).total_seconds() <= 45
    except (TypeError, ValueError):
        return False

def provider_reference(tournament: dict) -> str:
    """Keep the durable numeric ID in DB but carry optional community scope upstream."""
    remote_id = str(tournament.get("provider_tournament_id") or tournament.get("slug"))
    community = tournament.get("provider_subdomain")
    return f"{remote_id}@{community}" if tournament.get("provider_type") == "challonge" and community else remote_id


def serialize_provider_set_for_frontend(ps: ProviderSet) -> dict:
    """Map ProviderSet to frontend-compatible dict format."""
    return {
        "id": ps.id,
        "state": int(ps.state),
        "round": ps.round_name,
        "fullRoundText": ps.round_name,
        "identifier": ps.identifier,
        "event_id": ps.event_id,
        "event_name": ps.event_name,
        "phaseGroup": {
            "displayIdentifier": ps.phase_group
        },
        "p1": ps.entrant1.name if ps.entrant1 else "TBD",
        "p2": ps.entrant2.name if ps.entrant2 else "TBD",
        "p1_avatar": ps.entrant1.avatar_url if ps.entrant1 else None,
        "p2_avatar": ps.entrant2.avatar_url if ps.entrant2 else None,
        "p1_eid": ps.entrant1.id if ps.entrant1 else None,
        "p2_eid": ps.entrant2.id if ps.entrant2 else None,
    }


def serialize_tournament_for_frontend(info: ProviderTournament) -> dict:
    """Map ProviderTournament to a raw_data structure compatible with frontend ParticipantsTable."""
    return {
        "id": info.id,
        "name": info.name,
        "starts_at": info.starts_at,
        "provider_state": info.state,
        "group_stage_enabled": info.group_stage_enabled,
        "events": [
            {
                "id": ev.id,
                "name": ev.name,
                "videogame": {"name": ev.game or ""},
                "entrants": {
                    "nodes": [
                        {
                            "id": entrant.id,
                            "name": entrant.name,
                            "provider_user_id": entrant.user_id,
                            "participants": [
                                {
                                    "user": {
                                        "images": [
                                            {
                                                "type": "profile",
                                                "url": entrant.avatar_url or ""
                                            }
                                        ]
                                    }
                                }
                            ]
                        } for entrant in ev.entrants
                    ]
                }
            } for ev in info.events
        ]
    }


@router.get(
    "",
    summary="List all tournaments",
    response_model=TournamentsResponse,
    operation_id="listTournaments"
)
async def api_list_tournaments(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return all configured tournaments tracked in FNC database."""
    return TournamentsResponse(tournaments=await get_tournaments(_workspace(principal)))


@router.get(
    "/{slug:path}/provider-profile",
    response_model=ProviderCapabilityProfileResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get saved provider identity and local capability projection",
)
async def api_provider_profile(slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return local configuration only; this endpoint does not fetch a bracket."""
    tournament = await get_tournament(slug, _workspace(principal))
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    provider = await get_provider_for_tournament(slug, _workspace(principal))
    return tournament_provider_projection(tournament, provider)


@router.get("/{slug:path}/dispatcher-status", summary="Get actual dispatcher status for one tournament")
async def api_dispatcher_status(slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return persisted intent separately from whether the bot service is alive."""
    tournament = await get_tournament(slug, _workspace(principal))
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    master_enabled = (await get_setting("auto_dispatch_master_switch", "off") or "off").lower() == "on"
    heartbeat = await get_setting("auto_dispatcher_last_seen", None)
    configured = bool(tournament.get("auto_dispatch_enabled"))
    service_alive = _dispatcher_service_alive(heartbeat)
    if not configured:
        state, explanation = "paused_tournament", "Disabled for this tournament. Manual Calls remain available."
    elif not master_enabled:
        state, explanation = "paused_global", "Paused by the global Kill Switch. Manual Calls remain available."
    elif not service_alive:
        state, explanation = "service_offline", "Configured, but the Dispatcher service has not reported a recent heartbeat."
    else:
        state, explanation = "running", "The Dispatcher can evaluate fresh, eligible local matches for this tournament."
    return {
        "state": state,
        "configured": configured,
        "global_kill_switch_enabled": master_enabled,
        "service_alive": service_alive,
        "last_heartbeat_at": heartbeat,
        "explanation": explanation,
    }


@router.post(
    "",
    summary="Add a new tournament",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="addTournament"
)
async def api_add_tournament(body: AddTournamentRequest, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Add a tournament through its selected provider; persisted ownership is durable."""
    provider_type = body.provider_type or "startgg"
    slug = (body.identifier or body.slug or "").strip()
    if not slug: raise HTTPException(status_code=400, detail="Tournament identifier is required")
    # Capacity is checked before any provider request.  Re-importing the same
    # local projection does not consume another free-plan slot.
    workspace_id = _workspace(principal)
    if workspace_id is not None and not await get_tournament(slug, workspace_id):
        try:
            await require_workspace_capacity(workspace_id, "tournaments")
        except EntitlementLimitExceeded as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    if provider_type == "challonge":
        if not get_provider_feature_flags().challonge_read_enabled:
            raise HTTPException(status_code=409, detail="Challonge read support is not enabled for this Hub.")
        try:
            if not body.provider_account_id:
                raise HTTPException(status_code=422, detail="Select a Challonge integration account before importing.")
            resolved = await resolution_service.resolve(body.provider_account_id, slug, body.subdomain)
            stored = await persist_challonge_identity(
                resolved, locator_key=resolved["locator_key"], workspace_id=_workspace(principal)
            )
            return MessageResponse(message=f"Tournament {stored['name']} imported for identity preview only.", ok=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ChallongeRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except ChallongeError as exc:
            raise HTTPException(status_code=422, detail="Challonge request could not be completed.") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Challonge identity import failed.") from exc
    else:
        if "start.gg/" in slug:
            parts = slug.split("start.gg/")[-1].split("/")
            if len(parts) >= 2:
                slug = f"{parts[0]}/{parts[1]}"
        provider_id, provider_subdomain = slug, None

    provider = get_provider(provider_type)
    info = await provider.fetch_tournament(f"{provider_id}@{provider_subdomain}" if provider_type == "challonge" and provider_subdomain else provider_id)
    if not info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not find tournament on {provider.provider_name}: {slug}")

    event = info.events[0] if info.events else None
    compatible_raw = serialize_tournament_for_frontend(info)
    
    await upsert_tournament(
        slug=slug,
        name=info.name,
        event_name=event.name if event else None,
        event_id=str(event.id) if event else None,
        game=event.game if event else None,
        raw_data=json.dumps(compatible_raw), provider_type=provider_type,
        provider_tournament_id=str(provider_id), provider_subdomain=provider_subdomain,
        provider_account_id=body.provider_account_id, workspace_id=_workspace(principal),
    )
    # Cache the start.gg stream list so station settings can map to it later.
    await set_tournament_streams(slug, [
        {"id": s.id, "name": s.name, "source": s.source, "game": s.game}
        for s in info.streams
    ], _workspace(principal))
    try:
        if _workspace(principal):
            await sync_manager.sync_bracket(slug, workspace_id=_workspace(principal), reason="initial-import")
        else:
            await sync_manager.sync_bracket(slug, reason="initial-import")
    except Exception as exc:
        await set_tournament_sync_status(slug, False, str(exc), workspace_id=_workspace(principal))
        raise HTTPException(status_code=502, detail=f"Tournament saved but first sync failed: {exc}")
    return MessageResponse(message=f"Tournament {info.name} added successfully.", ok=True)


@router.get(
    "/{slug:path}/sets",
    summary="Fetch sets for a tournament",
    responses={502: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="fetchTournamentSets"
)
async def api_get_sets(slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Read SQLite cache; at most one stale-on-open refresh may run in background."""
    t = await get_tournament(slug, _workspace(principal))
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    workspace_id = _workspace(principal)
    scheduled = (
        await sync_manager.maybe_sync_on_stale_open(slug, workspace_id=workspace_id)
        if workspace_id else await sync_manager.maybe_sync_on_stale_open(slug)
    )
    snapshot = await get_bracket_snapshot(slug, _workspace(principal))
    return {
        **snapshot,
        "last_provider_sync": t.get("provider_last_synced_at"),
        "sync_status": t.get("provider_sync_status") or "stale",
        "stale_refresh_scheduled": scheduled,
        "economy_sync_on_stale_open": bool(t.get("economy_sync_on_stale_open", 1)),
    }


@router.post(
    "/{slug:path}/sync/bracket",
    summary="Explicitly synchronize a provider bracket",
    response_model=MessageResponse,
)
async def api_sync_bracket(slug: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """One rate-aware external refresh, initiated by the T.O. from the Hub."""
    tournament = await get_tournament(slug, _workspace(principal))
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.get("provider_type") == "challonge" and not get_provider_feature_flags().challonge_read_enabled:
        raise HTTPException(
            status_code=409,
            detail="Challonge read support is not enabled for this Hub.",
        )
    try:
        workspace_id = _workspace(principal)
        if workspace_id:
            await sync_manager.sync_bracket(slug, workspace_id=workspace_id, reason="manual")
        else:
            await sync_manager.sync_bracket(slug, reason="manual")
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _workspace(principal)})
        return MessageResponse(message="Bracket synchronized.", ok=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get(
    "/{slug:path}/sync-status",
    summary="Read local provider freshness and recovery status",
)
async def api_tournament_sync_status(slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """SQLite-only organizer diagnostics; this endpoint never polls a provider."""
    tournament = await get_tournament(slug, _workspace(principal))
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    state = await get_live_sync_state_v2(slug)
    return {
        "provider_type": tournament.get("provider_type") or "startgg",
        "last_provider_sync": tournament.get("provider_last_synced_at"),
        "sync_status": tournament.get("provider_sync_status") or "stale",
        "sync_error": tournament.get("provider_sync_error"),
        "mode": tournament.get("challonge_sync_mode") or "economy",
        "live_state": state or {},
        "provider_backed_actions_enabled": not bool(tournament.get("provider_sync_error")),
        "economy_message": "Remote changes appear on Sync now or a stale-open refresh." if (state or {}).get("mode") != "live" else None,
    }


@router.post(
    "/state-repair/challonge/dry-run",
    summary="Create a non-mutating Challonge false-live repair report",
)
async def api_challonge_state_repair_dry_run(body: ChallongeStateRepairDryRunRequest):
    """Consumes reviewed snapshot evidence only; never calls Challonge or applies a repair."""
    from backend.core.challonge_state_repair import dry_run
    try:
        report = await dry_run(
            snapshot_id=body.snapshot_id,
            snapshot_observed_at=body.snapshot_observed_at,
            provider_states=body.provider_states,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "report_id": report.report_id, "snapshot_id": report.snapshot_id,
        "snapshot_observed_at": report.snapshot_observed_at, "fingerprint": report.fingerprint,
        "rows": report.rows,
        "apply_available": False,
        "message": "Dry run only. Review the exact rows and approve a later apply explicitly.",
    }


@router.delete(
    "/{slug:path}/active-matches",
    dependencies=[Depends(verify_hub_password)],
    summary="Reset all hub matches for a tournament",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="resetTournamentHub"
)
async def api_reset_tournament_hub(slug: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Delete all active matches for the given tournament slug from local tracking. Requires admin password auth."""
    if not await get_tournament(slug, _workspace(principal)):
        raise HTTPException(status_code=404, detail="Tournament not found")
    await delete_tournament_active_matches(slug, _workspace(principal))
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _workspace(principal)})
    return MessageResponse(message="Hub matches reset", ok=True)


@router.delete(
    "/{slug:path}",
    summary="Delete a tournament",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="deleteTournament"
)
async def api_delete_tournament(slug: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Remove tournament configuration and associated data from database. Requires admin password auth."""
    try:
        if not await get_tournament(slug, _workspace(principal)):
            raise HTTPException(status_code=404, detail="Tournament not found")
        await delete_tournament(slug, _workspace(principal))
    except TournamentRemovalBlocked as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": _workspace(principal)})
    return MessageResponse(message="Deleted", ok=True)


@router.post(
    "/{slug:path}/refresh",
    summary="Refresh tournament data from Start.gg",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="refreshTournament"
)
async def api_refresh_tournament(slug: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Re-fetch tournament metadata from start.gg and update local settings. Requires admin password auth."""
    t = await get_tournament(slug, _workspace(principal))
    if t and t.get("provider_type") == "challonge":
        raise HTTPException(
            status_code=409,
            detail="Challonge identity imports do not refresh bracket or metadata in Phase 4.",
        )
    workspace_id = _workspace(principal)
    provider = await get_provider_for_tournament(slug, workspace_id) if workspace_id else await get_provider_for_tournament(slug)
    info = await provider.fetch_tournament(provider_reference(t or {"slug": slug}))
    if not info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not find tournament: {slug}")

    event = info.events[0] if info.events else None
    compatible_raw = serialize_tournament_for_frontend(info)

    await upsert_tournament(
        slug=slug,
        name=info.name,
        event_name=event.name if event else None,
        event_id=str(event.id) if event else None,
        game=event.game if event else None,
        raw_data=json.dumps(compatible_raw), provider_type=(t or {}).get("provider_type") or "startgg",
        provider_tournament_id=(t or {}).get("provider_tournament_id") or slug,
        provider_subdomain=(t or {}).get("provider_subdomain"),
        provider_account_id=(t or {}).get("provider_account_id"),
        workspace_id=_workspace(principal),
    )
    await set_tournament_streams(slug, [
        {"id": s.id, "name": s.name, "source": s.source, "game": s.game}
        for s in info.streams
    ], _workspace(principal))
    return MessageResponse(message="Tournament data refreshed.", ok=True)


@router.post(
    "/{slug:path}/start",
    summary="Start a Challonge tournament",
    response_model=MessageResponse,
)
async def api_start_tournament(slug: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Explicit organizer action. No automatic remote tournament state changes."""
    tournament = await get_tournament(slug, _workspace(principal))
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.get("provider_type") != "challonge":
        raise HTTPException(status_code=400, detail="Starting from Hub is currently available for Challonge tournaments only.")
    raise HTTPException(status_code=409, detail="Challonge lifecycle actions are not enabled in Phase 4.")


@router.get(
    "/{slug:path}/events",
    summary="List the events (games) under a tournament",
    responses={404: {"model": ErrorResponse}},
    operation_id="listTournamentEvents"
)
async def api_list_tournament_events(slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return the events under a tournament so the hub can populate the Event
    dropdown. Each event is a separate game/bracket (e.g. Tekken 8, SF6).

    The frontend uses this to scope attendees/matches by event and avoid
    cross-game contamination. Auto-select when there is exactly one event.
    """
    t = await get_tournament(slug, _workspace(principal))
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    try:
        raw = json.loads(t.get("raw_data") or "{}")
    except Exception:
        raw = {}
    events = [
        {
            "id": str(ev.get("id")),
            "name": ev.get("name") or "",
            "game": (ev.get("videogame") or {}).get("name") or "",
        }
        for ev in (raw.get("events") or [])
        if ev.get("id") is not None
    ]
    return {"events": events}


@router.get(
    "/{slug:path}/streams",
    summary="List start.gg streams configured on a tournament",
    responses={404: {"model": ErrorResponse}},
    operation_id="listTournamentStreams"
)
async def api_list_tournament_streams(slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return the cached list of start.gg streams for this tournament.

    Used by station settings to populate the stream-mapping dropdown.
    Refresh the tournament if you've added new streams in start.gg admin.
    """
    t = await get_tournament(slug, _workspace(principal))
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return {"streams": await get_tournament_streams(slug, _workspace(principal))}


@router.get(
    "/{slug:path}/verify-stream",
    summary="Preflight: verify local stream stations resolve to a live start.gg stream",
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    operation_id="verifyTournamentStream",
)
async def api_verify_tournament_stream(slug: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Live-check that each local stream station maps to a stream that still
    exists on start.gg, so the TO learns *before* a live wave whether the public
    📺 icon will actually render.

    Why a dedicated endpoint and not the cached `/streams`: streams can't be
    created via the API (Twitch/YouTube OAuth is browser-only), so the only
    failure mode is "TO forgot to link / unlinked it in start.gg admin." That's
    invisible to the cache, so we do a LIVE fetch here and refresh the cache as a
    side effect (station-mapping dropdowns get fresher data for free).

    On-demand by design — NOT polled. start.gg's 75/min budget is shared with the
    reconciliation loop, and this only changes when the TO edits start.gg admin,
    so the Hub calls it on mount + manual refresh, not on a timer.

    Gate semantics (warn-but-allow): `ok` drives a UI warning badge, it does NOT
    block streaming. Local stream stations carry OBS overlays, lobby creds, and
    routing that work WITHOUT a start.gg stream — only the public 📺 is affected.
    """
    t = await get_tournament(slug, _workspace(principal))
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    # LIVE fetch (not the cache) — this is the whole point of the preflight.
    workspace_id = _workspace(principal)
    provider = await get_provider_for_tournament(slug, workspace_id) if workspace_id else await get_provider_for_tournament(slug)
    try:
        live = await provider.fetch_streams(slug)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Provider error: {e}")

    live_streams = [{"id": str(s.id), "name": s.name, "source": s.source, "game": s.game} for s in live]
    # Refresh the cache so the station-mapping dropdown sees the same fresh list.
    await set_tournament_streams(slug, live_streams, _workspace(principal))

    live_by_id = {s["id"]: s for s in live_streams}
    # Advisory name-fallback only (names drift, IDs don't) — never auto-binds.
    live_by_name = {(s["name"] or "").strip().lower(): s for s in live_streams}

    stream_stations = [
        s for s in await get_stations(_workspace(principal))
        if s.get("is_stream_station") and not s.get("hidden")
    ]

    stations_out = []
    linked = 0
    for st in stream_stations:
        bound_id = str(st.get("startgg_stream_id") or "") or None
        matched = live_by_id.get(bound_id) if bound_id else None
        if bound_id and matched:
            status_str = "linked"
            linked += 1
        elif bound_id and not matched:
            status_str = "stale"   # bound to a start.gg stream that no longer exists
        else:
            status_str = "unmapped"  # TO never picked a start.gg stream for this station
        suggestion = None
        if status_str != "linked":
            hit = live_by_name.get((st.get("name") or "").strip().lower())
            if hit:
                suggestion = hit["id"]
        stations_out.append({
            "id": st["id"],
            "name": st.get("name"),
            "startgg_stream_id": bound_id,
            "status": status_str,
            "matched_stream": matched,
            "suggested_stream_id": suggestion,
        })

    # ok ⇔ at least one stream station resolves to a LIVE start.gg stream.
    # Every other branch warns (warn-but-allow): no stations is the *most* broken
    # case, so it must not silently pass while "exists-but-unlinked" warns.
    if not stream_stations:
        ok, reason, warning = False, "no_stream_stations", (
            "No stream station is configured in the Hub — the public 📺 and "
            "station routing are unavailable until you add one."
        )
    elif linked > 0:
        ok, reason, warning = True, "ok", None
    elif not live_streams:
        ok, reason, warning = False, "no_startgg_streams", (
            "No stream exists on start.gg — link a Twitch/YouTube channel in "
            "start.gg admin → Streams first (this can't be done via API)."
        )
    else:
        ok, reason, warning = False, "unlinked", (
            "Stream not linked on start.gg — map a Hub stream station to a "
            "start.gg stream in Station Settings first."
        )

    return {
        "ok": ok,
        "reason": reason,
        "warning": warning,
        "startgg_streams": live_streams,
        "stations": stations_out,
    }


@router.patch(
    "/{slug:path}/settings",
    summary="Update tournament settings",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="updateTournamentSettings"
)
async def api_update_tournament_settings(slug: str, body: PatchTournamentSettingsRequest, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Update auto-checkin timers and AI bot coordination limits. Requires admin password auth."""
    # exclude_unset (not exclude_none): persist exactly the fields the client sent,
    # and nothing else. Zeros/false already round-trip under either flag, but
    # exclude_none silently drops an explicitly-sent null — the same class of trap
    # we fixed in the matches PATCH (#8). This keeps the idiom consistent so a
    # future "send null to clear" can't be quietly swallowed. Unsent fields are
    # left untouched.
    d = body.model_dump(exclude_unset=True)
    if not await get_tournament(slug, _workspace(principal)):
        raise HTTPException(status_code=404, detail="Tournament not found")
    await update_tournament_settings(slug, _workspace(principal), **d)
    if d.get("auto_dispatch_enabled") is False:
        await cancel_pending_dispatcher_work(tournament_slug=slug)
    if "challonge_sync_mode" in d:
        await sync_manager.configure_live_schedule(slug, workspace_id=_workspace(principal))
    return MessageResponse(message="Updated", ok=True)


# ── Deprecated Overrides Endpoints (410 Gone) ──────────────────────────────

@router.get("/overrides/all", deprecated=True, summary="Get all player overrides (DEPRECATED)", operation_id="deprecatedGetOverrides")
async def deprecated_get_all_overrides():
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Deprecated. Use /api/players/overrides routes instead.")


@router.patch("/override/{id}", deprecated=True, summary="Save a player override (DEPRECATED)", operation_id="deprecatedSaveOverride")
async def deprecated_save_override(id: str):
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Deprecated. Use /api/players/overrides/{id} routes instead.")


@router.delete("/overrides", deprecated=True, summary="Clear all player overrides (DEPRECATED)", operation_id="deprecatedClearOverrides")
async def deprecated_clear_overrides():
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Deprecated. Use /api/players/overrides routes instead.")


@router.post("/avatar/{id}", deprecated=True, summary="Upload player avatar (DEPRECATED)", operation_id="deprecatedUploadAvatar")
async def deprecated_upload_avatar(id: str):
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Deprecated. Use /api/players/overrides/{id}/avatar routes instead.")
