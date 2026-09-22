"""Pure field-precedence resolver and presentation hook service for player presentation v1.

Precedence order:
override → confirmed player_profile / game_profile → provider snapshot → placeholder.
"""

from __future__ import annotations

import json
from typing import Any

from backend.core.contracts.player_presentation import (
    CharacterValue,
    EntrantPresentationRequest,
    EntrantScope,
    PlayerPresentationV1,
    PresentationField,
    ResolvedPresentation,
)

PLACEHOLDER_AVATAR = "/static/player_placeholder.jpg"


def resolve_presentation_v1(
    entrant_scope: EntrantScope,
    *,
    override: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    game_profile: dict[str, Any] | None = None,
    provider_snapshot: dict[str, Any] | None = None,
    linked: bool = False,
    player_profile_id: str | None = None,
) -> PlayerPresentationV1:
    """Pure, deterministic, no-I/O field-precedence resolver."""
    ov = override or {}
    prof = profile or {}
    gp = game_profile or {}
    prov = provider_snapshot or {}

    # 1. Display Name
    ov_name = str(ov.get("display_name") or ov.get("name") or "").strip()
    prof_name = str(prof.get("display_name") or prof.get("gamer_tag") or "").strip()
    prov_name = str(prov.get("display_name") or prov.get("name") or prov.get("gamerTag") or "").strip()

    if ov_name:
        display_name = PresentationField[str](value=ov_name, source="entrant_override")
    elif linked and prof_name:
        display_name = PresentationField[str](value=prof_name, source="player_profile")
    elif prov_name:
        display_name = PresentationField[str](value=prov_name, source="provider_snapshot")
    else:
        display_name = PresentationField[str](value="", source="placeholder")

    # 2. Prefix
    ov_prefix = str(ov.get("prefix") or ov.get("team") or "").strip()
    prof_prefix = str(prof.get("prefix") or prof.get("team") or "").strip()
    prov_prefix = str(prov.get("prefix") or prov.get("team") or "").strip()

    if ov_prefix:
        prefix = PresentationField[str](value=ov_prefix, source="entrant_override")
    elif linked and prof_prefix:
        prefix = PresentationField[str](value=prof_prefix, source="player_profile")
    elif prov_prefix:
        prefix = PresentationField[str](value=prov_prefix, source="provider_snapshot")
    else:
        prefix = PresentationField[str](value="", source="placeholder")

    # 3. Country
    ov_country = str(ov.get("country") or "").strip()
    prof_country = str(prof.get("country") or "").strip()
    prov_country = str(prov.get("country") or "").strip()

    if ov_country:
        country = PresentationField[str](value=ov_country, source="entrant_override")
    elif linked and prof_country:
        country = PresentationField[str](value=prof_country, source="player_profile")
    elif prov_country:
        country = PresentationField[str](value=prov_country, source="provider_snapshot")
    else:
        country = PresentationField[str](value="", source="placeholder")

    # 4. Avatar URL
    ov_avatar = str(ov.get("avatar_url") or "").strip()
    prof_avatar = str(prof.get("avatar_url") or prof.get("avatar_path") or "").strip()
    prov_avatar = str(prov.get("avatar_url") or prov.get("avatar") or "").strip()

    if ov_avatar:
        avatar_url = PresentationField[str](value=ov_avatar, source="entrant_override")
    elif linked and prof_avatar:
        avatar_url = PresentationField[str](value=prof_avatar, source="player_profile")
    elif prov_avatar:
        avatar_url = PresentationField[str](value=prov_avatar, source="provider_snapshot")
    else:
        avatar_url = PresentationField[str](value=PLACEHOLDER_AVATAR, source="placeholder")

    # 5. Character
    ov_char_id = str(ov.get("character_id") or "").strip()
    ov_char_name = str(ov.get("character_name") or ov.get("character") or "").strip()
    ov_char_image = str(ov.get("character_image_url") or "").strip()

    gp_char_id = str(gp.get("character_id") or "").strip()
    gp_char_name = str(gp.get("character_name") or "").strip()
    gp_char_image = str(gp.get("character_image_url") or "").strip()

    prov_char_id = str(prov.get("character_id") or "").strip()
    prov_char_name = str(prov.get("character_name") or prov.get("character") or "").strip()
    prov_char_image = str(prov.get("character_image_url") or "").strip()

    if ov_char_id or ov_char_name or ov_char_image:
        char_val = CharacterValue(name=ov_char_name, id=ov_char_id, image_url=ov_char_image)
        character = PresentationField[CharacterValue](value=char_val, source="entrant_override")
    elif linked and (gp_char_id or gp_char_name or gp_char_image):
        char_val = CharacterValue(name=gp_char_name, id=gp_char_id, image_url=gp_char_image)
        character = PresentationField[CharacterValue](value=char_val, source="player_profile")
    elif prov_char_id or prov_char_name or prov_char_image:
        char_val = CharacterValue(name=prov_char_name, id=prov_char_id, image_url=prov_char_image)
        character = PresentationField[CharacterValue](value=char_val, source="provider_snapshot")
    else:
        character = PresentationField[CharacterValue](value=CharacterValue(), source="placeholder")

    resolved = ResolvedPresentation(
        display_name=display_name,
        prefix=prefix,
        country=country,
        avatar_url=avatar_url,
        character=character,
    )

    resolved_profile_id = str(prof.get("id") or "") or player_profile_id

    return PlayerPresentationV1(
        version="v1",
        entrant=entrant_scope,
        player_profile_id=resolved_profile_id if (linked and resolved_profile_id) else None,
        linked=linked,
        presentation=resolved,
    )


async def resolve_entrant_presentation(
    workspace_id: str,
    request: EntrantPresentationRequest,
) -> PlayerPresentationV1:
    """Read-only presentation resolver using strictly local database state.

    Never issues provider API calls, WebSocket broadcasts, or database writes.
    """
    from backend.core import database
    from backend.core import player_profiles

    entrant_scope = EntrantScope(
        provider=request.provider,
        tournament_slug=request.tournament_slug,
        event_id=request.event_id,
        entrant_id=request.entrant_id,
    )

    # 1. Check scoped override first, fall back to legacy override
    override = await player_profiles.get_tournament_entrant_override(
        workspace_id=workspace_id,
        provider=request.provider,
        tournament_slug=request.tournament_slug,
        event_id=request.event_id,
        entrant_id=request.entrant_id,
    )
    if not override:
        legacy = await database.get_player_override(request.entrant_id, workspace_id)
        if legacy:
            override = {
                "display_name": legacy.get("display_name"),
                "prefix": legacy.get("team"),
                "country": legacy.get("country"),
                "avatar_url": legacy.get("avatar_url"),
                "character_id": legacy.get("character_id"),
                "character_name": legacy.get("character_name"),
                "character_image_url": legacy.get("character_image_url"),
            }

    # 2. Check confirmed linked profile
    profile = await player_profiles.get_entrant_linked_profile(
        workspace_id=workspace_id,
        tournament_slug=request.tournament_slug,
        entrant_id=request.entrant_id,
    )
    linked = profile is not None
    player_profile_id = profile.get("id") if profile else None

    # 3. Check game profile defaults if profile is linked
    game_profile: dict[str, Any] | None = None
    if profile and profile.get("id"):
        # Resolve tournament game to find game profile
        tourney = await database.get_tournament(request.tournament_slug, workspace_id)
        game_id = (tourney or {}).get("game") or ""
        if game_id:
            gp = await player_profiles.get_player_game_profile(workspace_id, profile["id"], game_id)
            if gp:
                defaults = await player_profiles.get_player_character_defaults(workspace_id, gp["id"])
                primary = next((d for d in defaults if d.get("is_primary")), defaults[0] if defaults else None)
                if primary:
                    game_profile = primary

    # 4. Extract provider snapshot data from tournament raw_data
    provider_snapshot: dict[str, Any] = {}
    tournament = await database.get_tournament(request.tournament_slug, workspace_id)
    if tournament:
        try:
            raw = json.loads(tournament.get("raw_data") or "{}")
            events = raw.get("events") or (raw.get("tournament") or {}).get("events") or []
            target_event = next(
                (ev for ev in events if str(ev.get("id") or "") == str(request.event_id)),
                events[0] if events else None,
            )
            if target_event:
                nodes = (target_event.get("entrants") or {}).get("nodes") or []
                node = next((n for n in nodes if str(n.get("id") or "") == str(request.entrant_id)), None)
                if node:
                    participants = node.get("participants") or []
                    part = participants[0] if participants and isinstance(participants[0], dict) else {}
                    user = part.get("user") if isinstance(part.get("user"), dict) else {}
                    loc = user.get("location") if isinstance(user.get("location"), dict) else {}
                    images = user.get("images") or []
                    avatar = next(
                        (img.get("url") for img in images if isinstance(img, dict) and img.get("type") == "profile" and img.get("url")),
                        None,
                    ) or next(
                        (img.get("url") for img in images if isinstance(img, dict) and img.get("url")),
                        None,
                    )
                    provider_snapshot = {
                        "name": node.get("name") or part.get("gamerTag"),
                        "prefix": node.get("prefix") or part.get("prefix"),
                        "country": node.get("country") or loc.get("country"),
                        "avatar_url": avatar,
                    }
        except (TypeError, ValueError, json.JSONDecodeError):
            provider_snapshot = {}

    return resolve_presentation_v1(
        entrant_scope,
        override=override,
        profile=profile,
        game_profile=game_profile,
        provider_snapshot=provider_snapshot,
        linked=linked,
        player_profile_id=player_profile_id,
    )


async def resolve_tournament_participants_presentation(
    workspace_id: str,
    tournament_slug: str,
    event_id: str | None = None,
) -> list[PlayerPresentationV1]:
    """Resolve presentation models for all entrants in a tournament/event in one batch read."""
    from backend.core import database
    from backend.core import player_profiles

    tournament = await database.get_tournament(tournament_slug, workspace_id)
    if not tournament:
        return []

    # Get confirmed links
    links = await database.get_tournament_player_links(tournament_slug, workspace_id)

    # Get scoped overrides
    scoped_overrides = await player_profiles.list_tournament_entrant_overrides(
        workspace_id=workspace_id,
        tournament_slug=tournament_slug,
        event_id=event_id,
    )
    overrides_by_entrant = {str(ov.get("entrant_id")): ov for ov in scoped_overrides}

    # Fallback to legacy overrides
    legacy_overrides = await database.get_all_player_overrides(workspace_id)

    # Parse entrants from tournament raw_data
    entrants: list[dict[str, Any]] = []
    try:
        raw = json.loads(tournament.get("raw_data") or "{}")
        events = raw.get("events") or (raw.get("tournament") or {}).get("events") or []
        if event_id:
            scoped_events = [ev for ev in events if str(ev.get("id") or "") == str(event_id)]
            if scoped_events:
                events = scoped_events
        for ev in events:
            ev_id = str(ev.get("id") or "")
            nodes = (ev.get("entrants") or {}).get("nodes") or []
            for node in nodes:
                if isinstance(node, dict) and node.get("id") is not None:
                    entrants.append({"event_id": ev_id, "node": node})
    except (TypeError, ValueError, json.JSONDecodeError):
        entrants = []

    provider_type = tournament.get("provider_type") or "startgg"
    tournament_game_id = str(tournament.get("game") or "").strip()
    results: list[PlayerPresentationV1] = []

    for item in entrants:
        ev_id = item["event_id"]
        node = item["node"]
        entrant_id = str(node["id"])

        entrant_scope = EntrantScope(
            provider=provider_type,
            tournament_slug=tournament_slug,
            event_id=ev_id,
            entrant_id=entrant_id,
        )

        override = overrides_by_entrant.get(entrant_id)
        if not override and entrant_id in legacy_overrides:
            leg = legacy_overrides[entrant_id]
            override = {
                "display_name": leg.get("display_name") or leg.get("name"),
                "prefix": leg.get("team") or leg.get("prefix"),
                "country": leg.get("country"),
                "avatar_url": leg.get("avatar_url"),
                "character_id": leg.get("character_id"),
                "character_name": leg.get("character_name") or leg.get("character"),
                "character_image_url": leg.get("character_image_url"),
            }

        link = links.get(entrant_id)
        linked = link is not None
        profile = link if linked else None
        game_profile: dict[str, Any] | None = None
        profile_id = str((link or {}).get("player_profile_id") or "").strip()
        if profile_id and tournament_game_id:
            gp = await player_profiles.get_player_game_profile(
                workspace_id, profile_id, tournament_game_id
            )
            if gp:
                defaults = await player_profiles.get_player_character_defaults(workspace_id, gp["id"])
                game_profile = next(
                    (item for item in defaults if item.get("is_primary")),
                    defaults[0] if defaults else None,
                )

        participants = node.get("participants") or []
        part = participants[0] if participants and isinstance(participants[0], dict) else {}
        user = part.get("user") if isinstance(part.get("user"), dict) else {}
        loc = user.get("location") if isinstance(user.get("location"), dict) else {}
        images = user.get("images") or []
        avatar = next(
            (img.get("url") for img in images if isinstance(img, dict) and img.get("type") == "profile" and img.get("url")),
            None,
        ) or next(
            (img.get("url") for img in images if isinstance(img, dict) and img.get("url")),
            None,
        )
        provider_snapshot = {
            "name": node.get("name") or part.get("gamerTag"),
            "prefix": node.get("prefix") or part.get("prefix"),
            "country": node.get("country") or loc.get("country"),
            "avatar_url": avatar,
        }

        resolved = resolve_presentation_v1(
            entrant_scope,
            override=override,
            profile=profile,
            game_profile=game_profile,
            provider_snapshot=provider_snapshot,
            linked=linked,
            player_profile_id=profile_id or None,
        )
        results.append(resolved)

    return results
