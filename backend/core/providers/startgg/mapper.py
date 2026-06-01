"""
Translates raw Start.gg GraphQL JSON responses into unified ProviderXxx contracts.
This is the ONLY module that knows the shape of Start.gg's nested JSON.
"""

from typing import Optional, List, Dict, Any
from backend.core.contracts.tournament_types import (
    ProviderTournament, ProviderEvent, ProviderEntrant,
    ProviderSet, ProviderSetState, ProviderStream,
)
from backend.core.providers.startgg.state_map import SGG_STATE_MAP


def map_stream(raw: Optional[Dict[str, Any]]) -> Optional[ProviderStream]:
    """Map a raw start.gg stream node to ProviderStream."""
    if not raw or raw.get("id") is None:
        return None
    return ProviderStream(
        id=str(raw["id"]),
        name=raw.get("streamName") or "Unnamed Stream",
        source=raw.get("streamSource"),
        game=raw.get("streamGame"),
    )


def _extract_avatar(participants: list) -> Optional[str]:
    """Extract profile avatar URL from start.gg participant data."""
    for p in (participants or []):
        user = p.get("user")
        if not user:
            continue
        images = user.get("images") or []
        for img in images:
            if img.get("type") == "profile":
                return img.get("url")
        if images:
            return images[0].get("url")
    return None


def _extract_user_id(participants: list) -> Optional[str]:
    """Extract the start.gg user.id of the first participant with a linked account.

    Entrants without a linked user (T.O.-added by name) return None and are
    treated as unreachable by the hub's coordination layer.
    """
    for p in (participants or []):
        user = p.get("user")
        if user and user.get("id") is not None:
            return str(user["id"])
    return None


def map_entrant(raw: Optional[Dict[str, Any]]) -> Optional[ProviderEntrant]:
    """Map a raw start.gg entrant node to ProviderEntrant."""
    if not raw:
        return None
    parts = raw.get("participants", []) or []
    return ProviderEntrant(
        id=str(raw["id"]),
        name=raw.get("name", "TBD"),
        avatar_url=_extract_avatar(parts),
        user_id=_extract_user_id(parts),
    )


def is_preview_set(raw: Dict[str, Any]) -> bool:
    """Preview sets (unresolved upstream) have non-numeric IDs like 'preview_xxx'
    and reject all mutations. Callers should filter them out before reporting."""
    sid = str(raw.get("id", ""))
    return sid.startswith("preview")


def map_set(raw: Dict[str, Any]) -> ProviderSet:
    """Map a raw start.gg set node to ProviderSet."""
    state_int = raw.get("state", 1)
    state = SGG_STATE_MAP.get(state_int, ProviderSetState.NOT_STARTED)

    slots = raw.get("slots", [])
    entrant1 = map_entrant(slots[0].get("entrant")) if len(slots) > 0 else None
    entrant2 = map_entrant(slots[1].get("entrant")) if len(slots) > 1 else None

    pg = raw.get("phaseGroup")
    phase_group = pg.get("displayIdentifier", "") if isinstance(pg, dict) else ""

    return ProviderSet(
        id=str(raw["id"]),
        state=state,
        round_name=raw.get("fullRoundText", ""),
        identifier=raw.get("identifier"),
        phase_group=phase_group,
        entrant1=entrant1,
        entrant2=entrant2,
    )


def map_tournament(raw: Dict[str, Any]) -> ProviderTournament:
    """Map a raw start.gg tournament response to ProviderTournament."""
    events = []
    for ev in raw.get("events", []):
        entrants = [
            map_entrant(n)
            for n in (ev.get("entrants", {}) or {}).get("nodes", [])
            if n is not None
        ]
        # Filter out None results
        entrants = [e for e in entrants if e is not None]
        events.append(ProviderEvent(
            id=str(ev["id"]),
            name=ev.get("name", ""),
            game=(ev.get("videogame") or {}).get("name"),
            entrants=entrants,
        ))
    streams = [s for s in (map_stream(s) for s in (raw.get("streams") or [])) if s]
    return ProviderTournament(
        id=str(raw.get("id", "")),
        name=raw.get("name", ""),
        events=events,
        streams=streams,
    )
