from fastapi import APIRouter, Request, HTTPException, Depends, status
import json
from typing import Dict, Any, List, Optional
from backend.core.database import (
    upsert_tournament, get_tournaments, get_tournament, delete_tournament,
    update_tournament_settings, delete_tournament_active_matches, sync_active_matches,
    get_all_player_overrides, set_tournament_streams, get_tournament_streams,
)
from backend.core.providers.registry import get_provider, get_provider_for_tournament
from backend.core.contracts.tournament_types import ProviderSet, ProviderTournament
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password
from backend.api.schemas import (
    AddTournamentRequest, PatchTournamentSettingsRequest, MessageResponse, ErrorResponse, TournamentsResponse
)

router = APIRouter(tags=["tournaments"])


def serialize_provider_set_for_frontend(ps: ProviderSet) -> dict:
    """Map ProviderSet to frontend-compatible dict format."""
    return {
        "id": ps.id,
        "state": int(ps.state),
        "round": ps.round_name,
        "fullRoundText": ps.round_name,
        "identifier": ps.identifier,
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
async def api_list_tournaments():
    """Return all configured tournaments tracked in FNC database."""
    return TournamentsResponse(tournaments=await get_tournaments())


@router.post(
    "",
    dependencies=[Depends(verify_hub_password)],
    summary="Add a new tournament",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="addTournament"
)
async def api_add_tournament(body: AddTournamentRequest):
    """Add a tournament by slug. Fetches info from Start.gg automatically. Requires admin password auth."""
    slug = body.slug.strip()
    if not slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slug required")

    if "start.gg/" in slug:
        parts = slug.split("start.gg/")[-1].split("/")
        if len(parts) >= 2:
            slug = f"{parts[0]}/{parts[1]}"

    provider = get_provider()
    info = await provider.fetch_tournament(slug)
    if not info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not find tournament on Start.gg: {slug}")

    event = info.events[0] if info.events else None
    compatible_raw = serialize_tournament_for_frontend(info)
    
    await upsert_tournament(
        slug=slug,
        name=info.name,
        event_name=event.name if event else None,
        event_id=str(event.id) if event else None,
        game=event.game if event else None,
        raw_data=json.dumps(compatible_raw)
    )
    # Cache the start.gg stream list so station settings can map to it later.
    await set_tournament_streams(slug, [
        {"id": s.id, "name": s.name, "source": s.source, "game": s.game}
        for s in info.streams
    ])
    return MessageResponse(message=f"Tournament {info.name} added successfully.", ok=True)


@router.get(
    "/{slug:path}/sets",
    summary="Fetch sets for a tournament",
    responses={502: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="fetchTournamentSets"
)
async def api_get_sets(slug: str):
    """Fetch all bracket sets from provider and sync local active matches database."""
    t = await get_tournament(slug)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    provider = await get_provider_for_tournament(slug)
    # Honor the TO's per-tournament override of the activity guard (default off).
    ignore_guard = bool(t.get("ignore_activity_guard"))
    try:
        provider_sets = await provider.fetch_sets(slug, ignore_activity_guard=ignore_guard)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Provider error: {e}")
    
    if provider_sets:
        await sync_active_matches(slug, provider_sets)

    serialized_sets = [serialize_provider_set_for_frontend(ps) for ps in provider_sets]
    return {"sets": serialized_sets}


@router.delete(
    "/{slug:path}/active-matches",
    dependencies=[Depends(verify_hub_password)],
    summary="Reset all hub matches for a tournament",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="resetTournamentHub"
)
async def api_reset_tournament_hub(slug: str):
    """Delete all active matches for the given tournament slug from local tracking. Requires admin password auth."""
    await delete_tournament_active_matches(slug)
    await hub_mgr.broadcast({"type": "match_update"})
    return MessageResponse(message="Hub matches reset", ok=True)


@router.delete(
    "/{slug:path}",
    dependencies=[Depends(verify_hub_password)],
    summary="Delete a tournament",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="deleteTournament"
)
async def api_delete_tournament(slug: str):
    """Remove tournament configuration and associated data from database. Requires admin password auth."""
    await delete_tournament(slug)
    return MessageResponse(message="Deleted", ok=True)


@router.post(
    "/{slug:path}/refresh",
    dependencies=[Depends(verify_hub_password)],
    summary="Refresh tournament data from Start.gg",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    operation_id="refreshTournament"
)
async def api_refresh_tournament(slug: str):
    """Re-fetch tournament metadata from start.gg and update local settings. Requires admin password auth."""
    provider = await get_provider_for_tournament(slug)
    info = await provider.fetch_tournament(slug)
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
        raw_data=json.dumps(compatible_raw)
    )
    await set_tournament_streams(slug, [
        {"id": s.id, "name": s.name, "source": s.source, "game": s.game}
        for s in info.streams
    ])
    return MessageResponse(message="Tournament data refreshed.", ok=True)


@router.get(
    "/{slug:path}/streams",
    summary="List start.gg streams configured on a tournament",
    responses={404: {"model": ErrorResponse}},
    operation_id="listTournamentStreams"
)
async def api_list_tournament_streams(slug: str):
    """Return the cached list of start.gg streams for this tournament.

    Used by station settings to populate the stream-mapping dropdown.
    Refresh the tournament if you've added new streams in start.gg admin.
    """
    t = await get_tournament(slug)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return {"streams": await get_tournament_streams(slug)}


@router.patch(
    "/{slug:path}/settings",
    dependencies=[Depends(verify_hub_password)],
    summary="Update tournament settings",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="updateTournamentSettings"
)
async def api_update_tournament_settings(slug: str, body: PatchTournamentSettingsRequest):
    """Update auto-checkin timers and AI bot coordination limits. Requires admin password auth."""
    d = body.model_dump(exclude_none=True)
    await update_tournament_settings(slug, **d)
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
