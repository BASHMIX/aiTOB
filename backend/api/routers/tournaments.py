from fastapi import APIRouter, Request, HTTPException, Depends
import json
from backend.core.database import (
    upsert_tournament, get_tournaments, get_tournament, delete_tournament,
    update_tournament_settings, delete_tournament_active_matches, sync_active_matches,
    get_all_player_overrides
)
from backend.core.startgg_client import get_client
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password
from backend.api.schemas import AddTournamentRequest

router = APIRouter(tags=["tournaments"])
sgg_client = get_client()


@router.get("", summary="List all tournaments")
async def api_list_tournaments():
    """Return all configured tournaments."""
    return {"tournaments": await get_tournaments()}


@router.post("",
             dependencies=[Depends(verify_hub_password)],
             summary="Add a new tournament")
async def api_add_tournament(body: AddTournamentRequest):
    """
    Add a tournament by slug. Fetches info from Start.gg automatically.
    Accepts either a slug (tournament/slug) or full URL.
    """
    slug = body.slug.strip()
    if not slug:
        raise HTTPException(400, "Slug required")

    if "start.gg/" in slug:
        parts = slug.split("start.gg/")[-1].split("/")
        if len(parts) >= 2:
            slug = f"{parts[0]}/{parts[1]}"

    info = await sgg_client.fetch_tournament_info(slug)
    if not info:
        raise HTTPException(404, f"Could not find tournament on Start.gg: {slug}")

    event = info.get("events", [{}])[0]
    await upsert_tournament(
        slug=slug,
        name=info.get("name"),
        event_name=event.get("name"),
        event_id=str(event.get("id")),
        game=event.get("videogame", {}).get("name"),
        raw_data=json.dumps(info)
    )
    return {"message": f"Tournament {info.get('name')} added successfully.", "slug": slug}


@router.get("/{slug}/sets", summary="Fetch sets for a tournament")
async def api_get_sets(slug: str):
    """Fetch all bracket sets from Start.gg and sync active matches."""
    t = await get_tournament(slug)
    if not t:
        raise HTTPException(404)

    sets = await sgg_client.fetch_tournament_sets(slug)
    if sets:
        await sync_active_matches(slug, sets)

    return {"sets": sets}


@router.post("/{slug}/reset-hub",
             dependencies=[Depends(verify_hub_password)],
             summary="Reset all hub matches for a tournament")
async def api_reset_tournament_hub(slug: str):
    """Delete all active matches for the given tournament slug."""
    await delete_tournament_active_matches(slug)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": "Hub matches reset", "ok": True}


@router.delete("/{slug}",
               dependencies=[Depends(verify_hub_password)],
               summary="Delete a tournament")
async def api_delete_tournament(slug: str):
    """Remove tournament configuration and associated data."""
    await delete_tournament(slug)
    return {"message": "Deleted"}


@router.post("/{slug}/refresh",
             dependencies=[Depends(verify_hub_password)],
             summary="Refresh tournament data from Start.gg")
async def api_refresh_tournament(slug: str):
    """Re-fetch tournament info from Start.gg and update local data."""
    info = await sgg_client.fetch_tournament_info(slug)
    if not info:
        raise HTTPException(404, f"Could not find tournament on Start.gg: {slug}")

    event = info.get("events", [{}])[0]
    await upsert_tournament(
        slug=slug,
        name=info.get("name"),
        event_name=event.get("name"),
        event_id=str(event.get("id")),
        game=event.get("videogame", {}).get("name"),
        raw_data=json.dumps(info)
    )
    return {"message": "Tournament data refreshed.", "ok": True}


@router.patch("/{slug}/settings",
              dependencies=[Depends(verify_hub_password)],
              summary="Update tournament settings")
async def api_update_tournament_settings(slug: str, request: Request):
    """Update auto-DQ timer and other tournament-specific settings."""
    d = await request.json()
    await update_tournament_settings(slug, **d)
    return {"message": "Updated"}


@router.get("/overrides/all", summary="Get all player overrides")
async def api_get_all_overrides():
    """Return all player name/avatar overrides."""
    from backend.core.database import get_all_player_overrides
    return await get_all_player_overrides()


@router.patch("/override/{id}",
              dependencies=[Depends(verify_hub_password)],
              summary="Save a player override")
async def api_patch_player_override(id: str, request: Request):
    """Override a player's display name or avatar URL."""
    from backend.core.database import save_player_override
    d = await request.json()
    await save_player_override(id, d)
    return {"message": "Override saved"}


@router.delete("/overrides",
               dependencies=[Depends(verify_hub_password)],
               summary="Clear all player overrides")
async def api_delete_all_player_overrides():
    from backend.core.database import delete_all_player_overrides
    await delete_all_player_overrides()
    return {"message": "All overrides cleared"}


@router.post("/avatar/{id}",
             dependencies=[Depends(verify_hub_password)],
             summary="Upload player avatar")
async def api_upload_player_avatar(id: str, request: Request):
    """Upload an avatar image for a player override."""
    from fastapi import UploadFile
    import os
    form = await request.form()
    file = form.get("avatar")
    if not isinstance(file, UploadFile):
        raise HTTPException(400, "No file uploaded")

    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
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
