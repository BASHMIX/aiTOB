from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import FileResponse
import os
from typing import Dict, Any, List, Optional
from backend.core.database import get_player, create_or_update_player, get_all_player_overrides, delete_all_player_overrides, get_player_override, save_player_override, delete_player_override
from backend.api.auth import verify_hub_password
from backend.api.schemas import CreatePlayerRequest, MessageResponse, ErrorResponse

router = APIRouter(tags=["players"])


@router.get("/{discord_id}/avatar", summary="Get player avatar image", operation_id="getPlayerAvatar")
async def api_player_avatar(discord_id: str):
    """Return a player's avatar image file or the default placeholder."""
    p = await get_player(discord_id)
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if p and p.get("avatar_path") and os.path.exists(p["avatar_path"]):
        return FileResponse(p["avatar_path"])
    return FileResponse(os.path.join(static_dir, "player_placeholder.jpg"))


@router.get("", summary="List all players", operation_id="listPlayers")
async def api_list_players():
    """Return all registered players from the database."""
    from backend.core.database import aiosqlite, DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players") as c:
            rows = await c.fetchall()
            return {"players": [dict(r) for r in rows]}


@router.post("", summary="Create or update a player", status_code=status.HTTP_201_CREATED, response_model=MessageResponse, operation_id="createPlayer")
async def api_create_player(body: CreatePlayerRequest):
    """Register a new player or update an existing one's information."""
    await create_or_update_player(**body.model_dump())
    return MessageResponse(message="Success", ok=True)


# ── Player Overrides (Unified & Standardized) ───────────────────────────────
# IMPORTANT: this entire static-path block MUST stay declared BEFORE the
# `GET /{discord_id}` catch-all below. Starlette matches routes in declaration
# order; a dynamic single-segment route would otherwise capture the literal
# string "overrides" as a discord_id and trip a 404. See the route-ordering
# regression that surfaced in ParticipantsTable.tsx.

@router.get(
    "/overrides",
    summary="Get all player overrides",
    response_model=Dict[str, Dict[str, Optional[str]]],
    operation_id="listPlayerOverrides"
)
async def api_get_overrides():
    """Return all player display name / avatar overrides. Accessible without admin authentication."""
    return await get_all_player_overrides()


@router.delete(
    "/overrides",
    dependencies=[Depends(verify_hub_password)],
    summary="Clear all overrides",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="clearPlayerOverrides"
)
async def api_delete_all_overrides():
    """Delete all configured player overrides from the database. Requires admin password authentication."""
    await delete_all_player_overrides()
    return MessageResponse(message="All overrides cleared", ok=True)


@router.get(
    "/overrides/{id}",
    summary="Get a single override",
    responses={404: {"model": ErrorResponse}},
    operation_id="getPlayerOverride"
)
async def api_get_override(id: str):
    """Retrieve details for a single configured player override by their entrant ID."""
    ov = await get_player_override(id)
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
async def api_patch_override(id: str, request: Request):
    """Save or update override properties for a player. Requires admin password authentication."""
    d = await request.json()
    validated = {
        k: str(v) for k, v in d.items()
        if k in ["name", "team", "country", "cfn", "avatar_url"]
    }
    await save_player_override(id, validated)
    return MessageResponse(message="Override saved", ok=True)


@router.delete(
    "/overrides/{id}",
    dependencies=[Depends(verify_hub_password)],
    summary="Delete a specific override",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="deletePlayerOverride"
)
async def api_delete_override(id: str):
    """Remove a configured player override. Requires admin password authentication."""
    await delete_player_override(id)
    return MessageResponse(message="Override deleted", ok=True)


@router.post(
    "/overrides/{id}/avatar",
    dependencies=[Depends(verify_hub_password)],
    summary="Upload player avatar",
    response_model=Dict[str, str],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    operation_id="uploadPlayerAvatar"
)
async def api_upload_avatar(id: str, request: Request):
    """Upload and set a custom avatar image override for a player. Requires admin password authentication."""
    from fastapi import UploadFile
    form = await request.form()
    file = form.get("avatar")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded")

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)

    ext = file.filename.split(".")[-1] if file.filename else "png"
    filename = f"avatar_{id}.{ext}"
    file_path = os.path.join(static_dir, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    avatar_url = f"/static/{filename}"
    await save_player_override(id, {"avatar_url": avatar_url})
    return {"avatar_url": avatar_url}


# ── Dynamic single-segment catch-all — keep last ────────────────────────────
# Declared after every static "/something" route above so it doesn't shadow them.
@router.get("/{discord_id}", summary="Get a player by Discord ID", operation_id="getPlayer")
async def api_get_player(discord_id: str):
    """Return a single player's details by their Discord ID."""
    p = await get_player(discord_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return p
