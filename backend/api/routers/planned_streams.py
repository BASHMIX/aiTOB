from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from backend.core.database import (
    add_planned_stream, remove_planned_stream, list_planned_streams,
    get_active_match, upsert_active_match, get_station_by_stream_id,
)
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password
from backend.api.schemas import (
    CreatePlannedStreamRequest, PlannedStreamsResponse,
    MessageResponse, ErrorResponse,
)

router = APIRouter(tags=["planned-streams"])


@router.get(
    "/planned-streams",
    summary="List planned-stream entries",
    response_model=PlannedStreamsResponse,
    operation_id="listPlannedStreams",
)
async def api_list_planned_streams(
    tournament_slug: Optional[str] = Query(default=None, description="Optional tournament slug filter"),
):
    """Return all sets flagged for inclusion on stream once they become live.

    Used by the bracket view to render the planned-stream star icon state.
    """
    return PlannedStreamsResponse(planned=await list_planned_streams(tournament_slug))


@router.post(
    "/planned-streams",
    dependencies=[Depends(verify_hub_password)],
    summary="Plan a set for stream",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    operation_id="planStreamSet",
)
async def api_add_planned_stream(body: CreatePlannedStreamRequest):
    """Flag a set (even a preview set or one not yet in the hub) for stream coverage.

    When the set becomes live (synced via /api/tournaments/{slug}/sets), the
    sync engine will mark it is_stream_match=true and, if a stream_id was
    supplied and a station is mapped to it, auto-assign that station.
    """
    await add_planned_stream(body.set_id, body.tournament_slug, body.stream_id, body.note)

    # If the set is ALREADY a tracked active match, promote it immediately
    # so the operator sees the change without waiting for the next sync.
    m = await get_active_match(body.set_id)
    if m:
        fields = {"is_stream_match": True}
        if body.stream_id and not m.get("station_id"):
            station = await get_station_by_stream_id(body.stream_id)
            if station:
                fields["station_id"] = station["id"]
        await upsert_active_match(body.set_id, **fields)
        await hub_mgr.broadcast({"type": "match_update"})

    return MessageResponse(message="Planned for stream", ok=True)


@router.delete(
    "/planned-streams/{set_id}",
    dependencies=[Depends(verify_hub_password)],
    summary="Remove a set from the planned-stream list",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="unplanStreamSet",
)
async def api_remove_planned_stream(set_id: str):
    """Unflag a set. Does NOT modify any active match's is_stream_match — toggle
    that separately via /api/active-matches/{set_id}/toggle-stream if needed."""
    await remove_planned_stream(set_id)
    return MessageResponse(message="Unplanned", ok=True)
