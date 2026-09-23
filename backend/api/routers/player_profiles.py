"""Player Profiles API router: Player Archive and versioned v1 Presentation Hook."""

from __future__ import annotations

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from backend.api.auth import require_permission
from backend.core.contracts.player_presentation import (
    EntrantPresentationRequest,
    EntrantScope,
    PlayerPresentationV1,
)
from backend.core.workspace_auth import SessionPrincipal
from backend.core import player_profiles
from backend.core.player_presentation import resolve_entrant_presentation

router = APIRouter(tags=["player-profiles"])


class CreateProfileRequest(BaseModel):
    display_name: str = Field(min_length=1)
    prefix: Optional[str] = None
    country: Optional[str] = None
    avatar_url: Optional[str] = None
    discord_id: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    prefix: Optional[str] = None
    country: Optional[str] = None
    avatar_url: Optional[str] = None
    discord_id: Optional[str] = None
    notes: Optional[str] = None


class CreateGameProfileRequest(BaseModel):
    game_id: str = Field(min_length=1)
    in_game_name: Optional[str] = None
    in_game_id: Optional[str] = None


class CreateCharacterDefaultRequest(BaseModel):
    character_id: str = Field(min_length=1)
    character_name: str = Field(min_length=1)
    character_image_url: Optional[str] = None
    is_primary: bool = True


# ── Versioned v1 Presentation Hook ──────────────────────────────────────────

@router.post(
    "/presentation/v1",
    response_model=PlayerPresentationV1,
    summary="Resolve entrant presentation model v1",
    operation_id="resolveEntrantPresentationV1",
)
async def api_resolve_presentation_v1_post(
    body: EntrantPresentationRequest,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
) -> PlayerPresentationV1:
    """Return local, read-only resolved presentation model for an entrant with field-level provenance."""
    scope = EntrantScope(
        provider=body.provider,
        tournament_slug=body.tournament_slug,
        event_id=body.event_id,
        entrant_id=body.entrant_id,
    )
    return await resolve_entrant_presentation(principal.workspace_id, scope)


@router.get(
    "/presentation/v1",
    response_model=PlayerPresentationV1,
    summary="Resolve entrant presentation model v1 by query",
    operation_id="queryEntrantPresentationV1",
)
async def api_resolve_presentation_v1_get(
    tournament_slug: str,
    event_id: str,
    entrant_id: str,
    provider: str = "startgg",
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
) -> PlayerPresentationV1:
    """Query parameter version of the v1 presentation hook."""
    scope = EntrantScope(
        provider=provider,
        tournament_slug=tournament_slug,
        event_id=event_id,
        entrant_id=entrant_id,
    )
    return await resolve_entrant_presentation(principal.workspace_id, scope)


# ── Player Archive Management ───────────────────────────────────────────────

@router.get(
    "",
    summary="List player profiles in workspace",
    operation_id="listPlayerProfiles",
)
async def api_list_profiles(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    query: Optional[str] = None,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """List profiles in the workspace with optional search."""
    profiles = await player_profiles.list_player_profiles(
        workspace_id=principal.workspace_id,
        limit=limit,
        offset=offset,
        query=query,
    )
    return {"profiles": profiles}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new player profile",
    operation_id="createPlayerProfile",
)
async def api_create_profile(
    body: CreateProfileRequest,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Create a new reusable player profile."""
    try:
        profile = await player_profiles.create_player_profile(
            workspace_id=principal.workspace_id,
            display_name=body.display_name,
            prefix=body.prefix,
            country=body.country,
            avatar_url=body.avatar_url,
            discord_id=body.discord_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return profile


@router.get(
    "/{profile_id}",
    summary="Get player profile detail",
    operation_id="getPlayerProfileDetail",
)
async def api_get_profile_detail(
    profile_id: str,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """Get player profile detail including linked game preferences and provider identities."""
    profile = await player_profiles.get_player_profile(profile_id, principal.workspace_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    provider_identities = await player_profiles.list_provider_identities(principal.workspace_id, profile_id)
    game_profiles = await player_profiles.list_player_game_profiles(principal.workspace_id, profile_id)

    for gp in game_profiles:
        gp["character_defaults"] = await player_profiles.get_player_character_defaults(
            principal.workspace_id, gp["id"]
        )

    return {
        **profile,
        "provider_identities": provider_identities,
        "game_profiles": game_profiles,
    }


@router.patch(
    "/{profile_id}",
    summary="Update player profile",
    operation_id="updatePlayerProfile",
)
async def api_update_profile(
    profile_id: str,
    body: UpdateProfileRequest,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Update editable fields of a player profile."""
    existing = await player_profiles.get_player_profile(profile_id, principal.workspace_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Player profile not found")

    data = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = await player_profiles.update_player_profile(profile_id, principal.workspace_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return updated


@router.post(
    "/{profile_id}/avatar",
    summary="Upload a persistent player-profile avatar",
)
async def api_upload_profile_avatar(
    profile_id: str,
    request: Request,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Normalize and store an avatar owned by a reusable player profile."""
    from starlette.datastructures import UploadFile

    profile = await player_profiles.get_player_profile(profile_id, principal.workspace_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    form = await request.form()
    file = form.get("avatar")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=400, detail="No avatar file uploaded")

    try:
        from backend.core.image_store import store_avatar
        from backend.core.image_utils import MAX_AVATAR_BYTES
        content = await file.read(MAX_AVATAR_BYTES + 1)
        avatar_url = await store_avatar(content, f"player-profile-{profile_id}", fallback_to_database=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    updated = await player_profiles.update_player_profile(
        profile_id, principal.workspace_id, {"avatar_url": avatar_url}
    )
    from backend.core.database import record_media_asset, retire_media_assets_for_urls
    await record_media_asset(
        workspace_id=principal.workspace_id,
        asset_type="player_profile_avatar",
        owner_type="player_profile",
        owner_id=profile_id,
        storage_url=avatar_url,
        storage_key=avatar_url.rsplit("/", 1)[-1] if avatar_url else None,
        mime_type=file.content_type,
        byte_size=len(content),
    )
    old_url = str(profile.get("avatar_url") or "")
    if old_url and old_url != avatar_url:
        await retire_media_assets_for_urls([old_url], principal.workspace_id)
    return {"avatar_url": avatar_url, "profile": updated}


@router.delete(
    "/{profile_id}",
    summary="Delete player profile",
    operation_id="deletePlayerProfile",
)
async def api_delete_profile(
    profile_id: str,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Delete a player profile and its associated game preferences."""
    existing = await player_profiles.get_player_profile(profile_id, principal.workspace_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Player profile not found")

    deleted = await player_profiles.delete_player_profile(profile_id, principal.workspace_id)
    return {"ok": deleted, "message": "Player profile deleted"}


# ── Game Preferences ────────────────────────────────────────────────────────

@router.post(
    "/{profile_id}/game-profiles",
    status_code=status.HTTP_201_CREATED,
    summary="Create or update game profile",
    operation_id="createPlayerGameProfile",
)
async def api_create_game_profile(
    profile_id: str,
    body: CreateGameProfileRequest,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Create or update a game preference profile for a player."""
    profile = await player_profiles.get_player_profile(profile_id, principal.workspace_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    gp = await player_profiles.set_player_game_profile(
        workspace_id=principal.workspace_id,
        player_profile_id=profile_id,
        game_id=body.game_id,
        in_game_name=body.in_game_name,
        in_game_id=body.in_game_id,
    )
    return gp


@router.get(
    "/{profile_id}/game-profiles",
    summary="List game profiles for player",
    operation_id="listPlayerGameProfiles",
)
async def api_list_game_profiles(
    profile_id: str,
    principal: SessionPrincipal = Depends(require_permission("workspace.read")),
):
    """List game preference profiles for a player."""
    profile = await player_profiles.get_player_profile(profile_id, principal.workspace_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    return {"game_profiles": await player_profiles.list_player_game_profiles(principal.workspace_id, profile_id)}


@router.post(
    "/{profile_id}/game-profiles/{game_profile_id}/character-defaults",
    status_code=status.HTTP_201_CREATED,
    summary="Add character default for game profile",
    operation_id="createPlayerCharacterDefault",
)
async def api_create_character_default(
    profile_id: str,
    game_profile_id: str,
    body: CreateCharacterDefaultRequest,
    principal: SessionPrincipal = Depends(require_permission("tournament.manage")),
):
    """Add or update character default for a game profile."""
    profile = await player_profiles.get_player_profile(profile_id, principal.workspace_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    cd = await player_profiles.set_player_character_default(
        workspace_id=principal.workspace_id,
        player_game_profile_id=game_profile_id,
        character_id=body.character_id,
        character_name=body.character_name,
        character_image_url=body.character_image_url,
        is_primary=body.is_primary,
    )
    return cd
