from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse
import os
from backend.core.database import get_player, create_or_update_player
from backend.api.auth import verify_hub_password
from backend.api.schemas import CreatePlayerRequest

router = APIRouter(tags=["players"])


@router.get("/{discord_id}/avatar", summary="Get player avatar image")
async def api_player_avatar(discord_id: str):
    """Return a player's avatar image file or the default placeholder."""
    p = await get_player(discord_id)
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if p and p.get("avatar_path") and os.path.exists(p["avatar_path"]):
        return FileResponse(p["avatar_path"])
    return FileResponse(os.path.join(static_dir, "player_placeholder.jpg"))


@router.get("", summary="List all players")
async def api_list_players():
    """Return all registered players from the database."""
    from backend.core.database import aiosqlite, DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players") as c:
            rows = await c.fetchall()
            return {"players": [dict(r) for r in rows]}


@router.get("/{discord_id}", summary="Get a player by Discord ID")
async def api_get_player(discord_id: str):
    """Return a single player's details."""
    p = await get_player(discord_id)
    if not p:
        raise HTTPException(404)
    return p


@router.post("", summary="Create or update a player")
async def api_create_player(body: CreatePlayerRequest):
    """Register a new player or update an existing one."""
    await create_or_update_player(**body.model_dump())
    return {"message": "Success"}


@router.get("/login/auth", summary="OAuth login link for Start.gg")
async def login(discord_id: str):
    """Redirect user to Start.gg OAuth authorization page."""
    from backend.core.database import get_setting
    client_id = await get_setting("STARTGG_CLIENT_ID")
    api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    redirect_uri = f"{api_base}/api/players/callback"
    return RedirectResponse(
        url=f"https://start.gg/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={discord_id}"
    )


@router.get("/callback", summary="OAuth callback from Start.gg")
async def callback(code: str, state: str):
    """Handle Start.gg OAuth callback and link Discord ID."""
    discord_id = state
    await create_or_update_player(discord_id=discord_id, registration_step="startgg_linked")
    return {"message": f"Linked to Discord ID {discord_id}. You can now close this tab and return to Discord."}


@router.get("/overrides", summary="Get all player overrides")
async def api_get_overrides():
    """Return all player display name / avatar overrides."""
    from backend.core.database import get_all_player_overrides
    return await get_all_player_overrides()


@router.delete("/overrides",
               dependencies=[Depends(verify_hub_password)],
               summary="Clear all overrides")
async def api_delete_all_overrides():
    from backend.core.database import delete_all_player_overrides
    await delete_all_player_overrides()
    return {"message": "All overrides cleared"}


@router.get("/override/{id}", summary="Get a single override")
async def api_get_override(id: str):
    from backend.core.database import get_player_override
    ov = await get_player_override(id)
    if not ov:
        raise HTTPException(404)
    return ov


@router.patch("/override/{id}",
              dependencies=[Depends(verify_hub_password)],
              summary="Save a player override")
async def api_patch_override(id: str, request: Request):
    from backend.core.database import save_player_override
    d = await request.json()
    await save_player_override(id, d)
    return {"message": "Override saved"}


@router.delete("/override/{id}",
               dependencies=[Depends(verify_hub_password)],
               summary="Delete a specific override")
async def api_delete_override(id: str):
    from backend.core.database import delete_player_override
    await delete_player_override(id)
    return {"message": "Override deleted"}


@router.post("/avatar/{id}",
             dependencies=[Depends(verify_hub_password)],
             summary="Upload player avatar")
async def api_upload_avatar(id: str, request: Request):
    """Upload an avatar image for a player."""
    from fastapi import UploadFile
    form = await request.form()
    file = form.get("avatar")
    if not isinstance(file, UploadFile):
        raise HTTPException(400, "No file uploaded")

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)

    ext = file.filename.split(".")[-1] if file.filename else "png"
    filename = f"avatar_{id}.{ext}"
    file_path = os.path.join(static_dir, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    avatar_url = f"/static/{filename}"

    from backend.core.database import save_player_override
    await save_player_override(id, {"avatar_url": avatar_url})

    return {"avatar_url": avatar_url}
