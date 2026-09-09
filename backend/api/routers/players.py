from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import FileResponse
import os
from typing import Dict, Any, List, Optional
from backend.core.database import get_player, create_or_update_player, get_all_player_overrides, delete_all_player_overrides, get_player_override, save_player_override, delete_player_override, get_tournament_player_links, link_tournament_entrant, unlink_tournament_entrant
from backend.api.auth import verify_hub_password, optional_session_principal, require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import CreatePlayerRequest, MessageResponse, ErrorResponse, TournamentPlayerLinkRequest

router = APIRouter(tags=["players"])


@router.get("/{discord_id}/avatar", summary="Get player avatar image", operation_id="getPlayerAvatar")
async def api_player_avatar(discord_id: str, principal: SessionPrincipal | None = Depends(optional_session_principal)):
    """Return a player's avatar image file or the default placeholder."""
    p = await get_player(discord_id, principal.workspace_id if principal else None)
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if p and p.get("avatar_path") and os.path.exists(p["avatar_path"]):
        return FileResponse(p["avatar_path"])
    return FileResponse(os.path.join(static_dir, "player_placeholder.jpg"))


@router.get("", summary="List all players", operation_id="listPlayers")
async def api_list_players(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return all registered players from the database."""
    from backend.core.database import list_players_for_workspace
    return {"players": await list_players_for_workspace(principal.workspace_id)}


@router.post("", summary="Create or update a player", status_code=status.HTTP_201_CREATED, response_model=MessageResponse, operation_id="createPlayer")
async def api_create_player(body: CreatePlayerRequest, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Register a new player or update an existing one's information."""
    try:
        await create_or_update_player(workspace_id=principal.workspace_id, **body.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return MessageResponse(message="Success", ok=True)


# ── Player Overrides (Unified & Standardized) ───────────────────────────────
# IMPORTANT: this entire static-path block MUST stay declared BEFORE the
# `GET /{discord_id}` catch-all below. Starlette matches routes in declaration
# order; a dynamic single-segment route would otherwise capture the literal
# string "overrides" as a discord_id and trip a 404. See the route-ordering
# regression that surfaced in ParticipantsTable.tsx.

@router.get("/links", summary="List confirmed player links for a tournament")
async def api_get_tournament_player_links(tournament_slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    return {"links": await get_tournament_player_links(tournament_slug, principal.workspace_id if principal else None)}


@router.put("/links", summary="Link an imported entrant to an aiTOB player")
async def api_link_tournament_entrant(body: TournamentPlayerLinkRequest, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    from backend.core.database import get_tournament
    if not await get_tournament(body.tournament_slug, principal.workspace_id):
        raise HTTPException(status_code=404, detail="Tournament not found")
    try:
        link = await link_tournament_entrant(body.tournament_slug, body.entrant_id, body.discord_id, principal.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "link": link}


@router.delete("/links", summary="Remove an imported entrant player link")
async def api_unlink_tournament_entrant(tournament_slug: str, entrant_id: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    from backend.core.database import get_tournament
    if not await get_tournament(tournament_slug, principal.workspace_id):
        raise HTTPException(status_code=404, detail="Tournament not found")
    if not await unlink_tournament_entrant(tournament_slug, entrant_id, principal.workspace_id):
        raise HTTPException(status_code=404, detail="Player link not found")
    return MessageResponse(message="Player link removed", ok=True)

@router.get(
    "/overrides",
    summary="Get all player overrides",
    response_model=Dict[str, Dict[str, Optional[str]]],
    operation_id="listPlayerOverrides"
)
async def api_get_overrides(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return all player display name / avatar overrides. Accessible without admin authentication."""
    return await get_all_player_overrides(principal.workspace_id)


@router.delete(
    "/overrides",
    dependencies=[Depends(verify_hub_password)],
    summary="Clear all overrides",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="clearPlayerOverrides"
)
async def api_delete_all_overrides(principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Delete all configured player overrides from the database. Requires admin password authentication."""
    await delete_all_player_overrides(principal.workspace_id)
    return MessageResponse(message="All overrides cleared", ok=True)


@router.get(
    "/overrides/{id}",
    summary="Get a single override",
    responses={404: {"model": ErrorResponse}},
    operation_id="getPlayerOverride"
)
async def api_get_override(id: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Retrieve details for a single configured player override by their entrant ID."""
    ov = await get_player_override(id, principal.workspace_id)
    if not ov:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
    return ov


@router.patch(
    "/overrides/{id}",
    dependencies=[Depends(verify_hub_password)],
    summary="Save a player override",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="savePlayerOverride"
)
async def api_patch_override(id: str, request: Request, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Save or update override properties for a player. Requires admin password authentication."""
    d = await request.json()
    validated = {
        k: str(v) for k, v in d.items()
        if k in ["name", "team", "country", "cfn", "avatar_url"]
    }
    try:
        await save_player_override(id, validated, principal.workspace_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return MessageResponse(message="Override saved", ok=True)


@router.delete(
    "/overrides/{id}",
    dependencies=[Depends(verify_hub_password)],
    summary="Delete a specific override",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="deletePlayerOverride"
)
async def api_delete_override(id: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Remove a configured player override. Requires admin password authentication."""
    await delete_player_override(id, principal.workspace_id)
    return MessageResponse(message="Override deleted", ok=True)


@router.post(
    "/overrides/{id}/avatar",
    dependencies=[Depends(verify_hub_password)],
    summary="Upload player avatar",
    response_model=Dict[str, str],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    operation_id="uploadPlayerAvatar"
)
async def api_upload_avatar(id: str, request: Request, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    """Upload and set a custom avatar image override for a player. Requires admin password authentication."""
    # request.form() yields Starlette's runtime UploadFile implementation.
    # FastAPI's exported subclass fails this isinstance check on recent
    # Starlette versions even when the browser sent a valid multipart file.
    from starlette.datastructures import UploadFile
    form = await request.form()
    file = form.get("avatar")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded")

    from backend.core.image_store import store_avatar
    try:
        # Bound the read before decoding; one extra byte distinguishes an exact
        # limit from an oversized upload without buffering an arbitrary body.
        from backend.core.image_utils import MAX_AVATAR_BYTES
        content = await file.read(MAX_AVATAR_BYTES + 1)
        avatar_url = await store_avatar(content, f"participant-{id}")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        await save_player_override(id, {"avatar_url": avatar_url}, principal.workspace_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    from backend.core.database import record_media_asset
    await record_media_asset(
        workspace_id=principal.workspace_id,
        asset_type="participant_avatar",
        owner_type="player_override",
        owner_id=id,
        storage_url=avatar_url,
        storage_key=avatar_url.rsplit("/", 1)[-1] if avatar_url else None,
        mime_type=getattr(file, "content_type", None),
        byte_size=len(content),
    )
    return {"avatar_url": avatar_url}


# ── Dynamic single-segment catch-all — keep last ────────────────────────────
# Declared after every static "/something" route above so it doesn't shadow them.
@router.get("/{discord_id}", summary="Get a player by Discord ID", operation_id="getPlayer")
async def api_get_player(discord_id: str, principal: SessionPrincipal | None = Depends(optional_session_principal)):
    """Return a single player's details by their Discord ID."""
    p = await get_player(discord_id, principal.workspace_id if principal else None)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return p
