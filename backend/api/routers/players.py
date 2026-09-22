from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import FileResponse
import json
import os
from typing import Dict, Any, List, Optional
from backend.core.database import (
    get_player, create_or_update_player, get_all_player_overrides,
    delete_all_player_overrides, get_player_override, save_player_override,
    delete_player_override, get_tournament_player_links, link_tournament_entrant,
    unlink_tournament_entrant, get_player_avatar_urls, set_player_avatar,
    retire_media_assets_for_urls, get_tournament, get_tournament_game_metadata,
)
from backend.api.auth import verify_hub_password, optional_session_principal, require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import CreatePlayerRequest, MessageResponse, ErrorResponse, TournamentPlayerLinkRequest
from backend.core.contracts.player_presentation import PlayerPresentationV1

router = APIRouter(tags=["players"])


async def _broadcast_override_update(workspace_id: str) -> None:
    """Refresh both organizer projections and authenticated OBS viewers."""
    from backend.api.ws_manager import manager
    message = {"type": "match_update"}
    await manager.broadcast({**message, "_workspace_id": workspace_id})
    await manager.broadcast_to_workspace_overlays(workspace_id, message)


async def _canonical_character_override(
    entrant_id: str,
    payload: dict,
    workspace_id: str,
) -> dict[str, str]:
    """Validate a character choice against the exact selected Start.gg Event."""
    character_id = str(payload.get("character_id") or "").strip()
    character_name = str(payload.get("character") or "").strip()
    character_image = str(payload.get("character_image_url") or "").strip()
    if not character_id and not character_name and not character_image:
        return {"character": "", "character_id": "", "character_image_url": ""}
    if not character_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select a character from the Start.gg Event catalog.",
        )

    tournament_slug = str(payload.get("tournament_slug") or "").strip()
    event_id = str(payload.get("event_id") or "").strip()
    if not tournament_slug or not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tournament and Event are required when selecting a character.",
        )
    tournament = await get_tournament(tournament_slug, workspace_id)
    if not tournament or tournament.get("provider_type") != "startgg":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Start.gg tournament not found.")

    try:
        raw = json.loads(tournament.get("raw_data") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        raw = {}
    events = raw.get("events") or (raw.get("tournament") or {}).get("events") or []
    selected_event = next(
        (event for event in events if str(event.get("id")) == event_id),
        None,
    )
    if not selected_event:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected Event does not belong to this tournament.")
    entrant_nodes = ((selected_event.get("entrants") or {}).get("nodes") or [])
    if entrant_nodes and not any(str(entrant.get("id")) == str(entrant_id) for entrant in entrant_nodes):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Player does not belong to the selected Event.")

    metadata = await get_tournament_game_metadata(tournament_slug, event_id, workspace_id)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Refresh Metadata before selecting a character.",
        )
    character = next(
        (
            item for item in metadata.get("characters") or []
            if isinstance(item, dict) and str(item.get("id")) == character_id
        ),
        None,
    )
    if not character:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character is not part of the selected Start.gg Event catalog.",
        )
    images = character.get("images") or []
    image_url = str(
        character.get("image_url")
        or next((image.get("url") for image in images if isinstance(image, dict) and image.get("url")), "")
        or ""
    )
    return {
        "character": str(character.get("name") or character_name),
        "character_id": str(character["id"]),
        "character_image_url": image_url,
    }


async def _validate_tournament_override_scope(
    *,
    entrant_id: str,
    tournament_slug: str,
    event_id: str,
    provider: str,
    workspace_id: str,
) -> None:
    """Ensure an entrant override is attached to a real event in this workspace."""
    tournament = await get_tournament(tournament_slug, workspace_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found.")
    expected_provider = str(tournament.get("provider_type") or "startgg").strip().lower()
    if provider.strip().lower() != expected_provider:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider does not match the tournament.")
    try:
        raw = json.loads(tournament.get("raw_data") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        raw = {}
    events = raw.get("events") or (raw.get("tournament") or {}).get("events") or []
    selected_event = next((event for event in events if str(event.get("id")) == str(event_id)), None)
    if not selected_event:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected Event does not belong to this tournament.")
    entrant_nodes = ((selected_event.get("entrants") or {}).get("nodes") or [])
    if entrant_id and entrant_nodes and not any(str(entrant.get("id")) == str(entrant_id) for entrant in entrant_nodes):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Player does not belong to the selected Event.")


def _scoped_override_response(override: dict[str, Any]) -> dict[str, Any]:
    """Keep the Participants response shape while its storage is event-scoped."""
    return {
        "id": override.get("entrant_id"),
        "name": override.get("display_name"),
        "display_name": override.get("display_name"),
        "team": override.get("prefix"),
        "prefix": override.get("prefix"),
        "country": override.get("country"),
        "avatar_url": override.get("avatar_url"),
        "character": override.get("character_name"),
        "character_name": override.get("character_name"),
        "character_id": override.get("character_id"),
        "character_image_url": override.get("character_image_url"),
        "notes": override.get("notes"),
    }


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
        payload = body.model_dump()
        payload["gamertag"] = payload.get("gamertag") or payload.get("name") or None
        payload["prefix"] = payload.get("prefix") or payload.get("team") or None
        await create_or_update_player(workspace_id=principal.workspace_id, **payload)
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
async def api_get_overrides(
    tournament_slug: Optional[str] = None,
    event_id: Optional[str] = None,
    provider: str = "startgg",
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """Return legacy overrides or the explicitly requested event-scoped overrides."""
    if tournament_slug or event_id:
        if not tournament_slug or not event_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament and Event are required together.")
        from backend.core.player_profiles import list_tournament_entrant_overrides
        scoped = await list_tournament_entrant_overrides(
            principal.workspace_id, tournament_slug, event_id, provider
        )
        return {str(row["entrant_id"]): _scoped_override_response(row) for row in scoped}
    return await get_all_player_overrides(principal.workspace_id)


@router.delete(
    "/overrides",
    dependencies=[Depends(verify_hub_password)],
    summary="Clear all overrides",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="clearPlayerOverrides"
)
async def api_delete_all_overrides(
    tournament_slug: Optional[str] = None,
    event_id: Optional[str] = None,
    provider: str = "startgg",
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Clear legacy overrides or the explicitly requested event-scoped overrides."""
    if bool(tournament_slug) != bool(event_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament and Event are required together.")
    if tournament_slug and event_id:
        await _validate_tournament_override_scope(
            entrant_id="", tournament_slug=tournament_slug, event_id=event_id,
            provider=provider, workspace_id=principal.workspace_id,
        )
        from backend.core.player_profiles import list_tournament_entrant_overrides, delete_tournament_entrant_override
        scoped = await list_tournament_entrant_overrides(
            principal.workspace_id, tournament_slug, event_id, provider
        )
        for row in scoped:
            await delete_tournament_entrant_override(
                principal.workspace_id, provider, tournament_slug, event_id, str(row["entrant_id"])
            )
    else:
        await delete_all_player_overrides(principal.workspace_id)
        await _broadcast_override_update(principal.workspace_id)
    return MessageResponse(message="All overrides cleared", ok=True)


@router.get(
    "/overrides/{id}",
    summary="Get a single override",
    responses={404: {"model": ErrorResponse}},
    operation_id="getPlayerOverride"
)
async def api_get_override(
    id: str,
    tournament_slug: Optional[str] = None,
    event_id: Optional[str] = None,
    provider: str = "startgg",
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """Retrieve a legacy override or the explicitly requested event-scoped override."""
    if bool(tournament_slug) != bool(event_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament and Event are required together.")
    if tournament_slug and event_id:
        from backend.core.player_profiles import get_tournament_entrant_override
        scoped = await get_tournament_entrant_override(
            principal.workspace_id, provider, tournament_slug, event_id, id
        )
        if not scoped:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
        return _scoped_override_response(scoped)
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
    """Save one legacy override or one explicit event-scoped override, never both."""
    d = await request.json()
    validated = {
        k: str(v) for k, v in d.items()
        if k in ["name", "prefix", "country", "cfn", "avatar_url"]
    }
    if "prefix" not in validated and "team" in d:
        validated["prefix"] = str(d["team"])
    if any(key in d for key in ("character", "character_id", "character_image_url")):
        validated.update(await _canonical_character_override(id, d, principal.workspace_id))
    t_slug = str(d.get("tournament_slug") or "").strip()
    ev_id = str(d.get("event_id") or "").strip()
    provider = str(d.get("provider") or "startgg").strip().lower()
    if bool(t_slug) != bool(ev_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament and Event are required together.")
    try:
        if t_slug:
            await _validate_tournament_override_scope(
                entrant_id=id, tournament_slug=t_slug, event_id=ev_id,
                provider=provider, workspace_id=principal.workspace_id,
            )
            from backend.core.player_profiles import set_tournament_entrant_override
            await set_tournament_entrant_override(
                workspace_id=principal.workspace_id, provider=provider,
                tournament_slug=t_slug, event_id=ev_id, entrant_id=id,
                data=validated, updated_by=principal.user_id,
            )
        else:
            await save_player_override(id, validated, principal.workspace_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not t_slug:
        await _broadcast_override_update(principal.workspace_id)
    return MessageResponse(message="Override saved", ok=True)


@router.delete(
    "/overrides/{id}",
    dependencies=[Depends(verify_hub_password)],
    summary="Delete a specific override",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="deletePlayerOverride"
)
async def api_delete_override(
    id: str,
    tournament_slug: Optional[str] = None,
    event_id: Optional[str] = None,
    provider: Optional[str] = "startgg",
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Reset one legacy override or one explicit event-scoped override, never both."""
    if bool(tournament_slug) != bool(event_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament and Event are required together.")
    if tournament_slug and event_id:
        await _validate_tournament_override_scope(
            entrant_id=id, tournament_slug=tournament_slug, event_id=event_id,
            provider=provider or "startgg", workspace_id=principal.workspace_id,
        )
        from backend.core.player_profiles import delete_tournament_entrant_override
        await delete_tournament_entrant_override(
            workspace_id=principal.workspace_id,
            provider=provider or "startgg",
            tournament_slug=tournament_slug,
            event_id=event_id,
            entrant_id=id,
        )
    else:
        await delete_player_override(id, principal.workspace_id)
        await _broadcast_override_update(principal.workspace_id)
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

    from backend.core.image_store import store_avatar, delete_stored_avatar
    linked_discord_id = str(form.get("discord_id") or "").strip() or None
    tournament_slug = str(form.get("tournament_slug") or "").strip()
    event_id = str(form.get("event_id") or "").strip()
    provider = str(form.get("provider") or "startgg").strip().lower()
    if bool(tournament_slug) != bool(event_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament and Event are required together.")
    old_override = await get_player_override(id, principal.workspace_id)
    old_urls: list[str] = []
    if old_override and old_override.get("avatar_url"):
        old_urls.append(str(old_override["avatar_url"]))
    if linked_discord_id:
        old_urls.extend(await get_player_avatar_urls(linked_discord_id, principal.workspace_id))
    try:
        # Bound the read before decoding; one extra byte distinguishes an exact
        # limit from an oversized upload without buffering an arbitrary body.
        from backend.core.image_utils import MAX_AVATAR_BYTES
        content = await file.read(MAX_AVATAR_BYTES + 1)
        # A linked Discord player and a Hub upload must share one deterministic
        # owner key so uploading from either channel replaces the same object.
        owner_key = f"player-{linked_discord_id}" if linked_discord_id else f"entrant-{id}"
        avatar_url = await store_avatar(content, owner_key, fallback_to_database=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if tournament_slug:
        await _validate_tournament_override_scope(
            entrant_id=id, tournament_slug=tournament_slug, event_id=event_id,
            provider=provider, workspace_id=principal.workspace_id,
        )
        from backend.core.player_profiles import get_tournament_entrant_override, set_tournament_entrant_override
        scoped_before = await get_tournament_entrant_override(
            principal.workspace_id, provider, tournament_slug, event_id, id
        )
        await set_tournament_entrant_override(
            workspace_id=principal.workspace_id, provider=provider,
            tournament_slug=tournament_slug, event_id=event_id, entrant_id=id,
            data={"avatar_url": avatar_url}, updated_by=principal.user_id,
        )
        from backend.core.database import record_media_asset
        await record_media_asset(
            workspace_id=principal.workspace_id,
            asset_type="participant_avatar",
            owner_type="tournament_entrant_override",
            owner_id=str((scoped_before or {}).get("id") or id),
            storage_url=avatar_url,
            storage_key=avatar_url.rsplit("/", 1)[-1] if avatar_url else None,
            mime_type=getattr(file, "content_type", None), byte_size=len(content),
        )
        # The old object may still be referenced by a profile, another event, or
        # an archived projection. A later asset cleanup pass owns its retirement.
        return {"avatar_url": avatar_url}
    try:
        await save_player_override(id, {"avatar_url": avatar_url}, principal.workspace_id)
        if linked_discord_id:
            await set_player_avatar(linked_discord_id, avatar_url, principal.workspace_id)
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
    await retire_media_assets_for_urls([url for url in old_urls if url != avatar_url], principal.workspace_id)
    for old_url in old_urls:
        if old_url != avatar_url:
            await delete_stored_avatar(old_url, preserve_url=avatar_url)
    return {"avatar_url": avatar_url}


@router.get(
    "/presentation",
    summary="Get tournament participants presentation",
    response_model=List[PlayerPresentationV1],
    operation_id="getTournamentParticipantsPresentation",
)
async def api_get_tournament_participants_presentation(
    tournament_slug: str,
    event_id: Optional[str] = None,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """Return resolved presentation models for all entrants in a tournament/event."""
    from backend.core.player_presentation import resolve_tournament_participants_presentation
    return await resolve_tournament_participants_presentation(
        workspace_id=principal.workspace_id,
        tournament_slug=tournament_slug,
        event_id=event_id,
    )


@router.get(
    "/presentation/{tournament_slug}",
    summary="Get tournament participants presentation by tournament slug",
    response_model=List[PlayerPresentationV1],
    operation_id="getTournamentParticipantsPresentationBySlug",
)
async def api_get_tournament_participants_presentation_by_slug(
    tournament_slug: str,
    event_id: Optional[str] = None,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """Return resolved presentation models for all entrants in a tournament/event by slug."""
    from backend.core.player_presentation import resolve_tournament_participants_presentation
    return await resolve_tournament_participants_presentation(
        workspace_id=principal.workspace_id,
        tournament_slug=tournament_slug,
        event_id=event_id,
    )


# ── Dynamic single-segment catch-all — keep last ────────────────────────────
# Declared after every static "/something" route above so it doesn't shadow them.
@router.get("/{discord_id}", summary="Get a player by Discord ID", operation_id="getPlayer")
async def api_get_player(discord_id: str, principal: SessionPrincipal | None = Depends(optional_session_principal)):
    """Return a single player's details by their Discord ID."""
    p = await get_player(discord_id, principal.workspace_id if principal else None)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return p
