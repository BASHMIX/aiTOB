"""
Translates raw Start.gg GraphQL JSON responses into unified ProviderXxx contracts.
This is the ONLY module that knows the shape of Start.gg's nested JSON.
"""

from typing import Optional, List, Dict, Any
from datetime import UTC, datetime
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


def _extract_profile_fields(participants: list, profile_by_user_id: Optional[dict[str, dict[str, Any]]] = None) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return point-in-time prefix/tag and optional Capcom CFN fields."""
    for participant in (participants or []):
        if not isinstance(participant, dict):
            continue
        user = participant.get("user") if isinstance(participant.get("user"), dict) else {}
        profile = (profile_by_user_id or {}).get(str(user.get("id") or ""), {})
        participant_player = participant.get("player") if isinstance(participant.get("player"), dict) else {}
        profile_player = profile.get("player") if isinstance(profile.get("player"), dict) else {}
        prefix = (
            participant.get("prefix")
            or participant_player.get("prefix")
            or profile.get("prefix")
            or profile_player.get("prefix")
        )
        gamertag = (
            participant.get("gamerTag")
            or participant.get("gamertag")
            or participant_player.get("gamerTag")
            or profile.get("gamerTag")
            or profile_player.get("gamerTag")
        )
        accounts = participant.get("connectedAccounts") or {}
        cfn = None
        if isinstance(accounts, dict):
            capcom = accounts.get("capcom") or accounts.get("CAPCOM")
            if isinstance(capcom, dict):
                cfn = capcom.get("value") or capcom.get("id")
        return (
            str(prefix).strip() if prefix not in (None, "") else None,
            str(gamertag).strip() if gamertag not in (None, "") else None,
            str(cfn).strip() if cfn not in (None, "") else None,
        )
    return None, None, None


def _extract_country(participants: list, profile_by_user_id: Optional[dict[str, dict[str, Any]]] = None) -> Optional[str]:
    """Return the public country from the participant's Start.gg user profile."""
    for participant in (participants or []):
        if not isinstance(participant, dict):
            continue
        user = participant.get("user") if isinstance(participant.get("user"), dict) else {}
        profile = (profile_by_user_id or {}).get(str(user.get("id") or ""), {})
        location = user.get("location") if isinstance(user.get("location"), dict) else {}
        profile_user = profile.get("user") if isinstance(profile.get("user"), dict) else {}
        profile_location = profile_user.get("location") if isinstance(profile_user.get("location"), dict) else {}
        country = (
            participant.get("country")
            or location.get("country")
            or profile.get("country")
            or profile_location.get("country")
        )
        if country not in (None, ""):
            return str(country).strip()
    return None


def map_entrant(raw: Optional[Dict[str, Any]], profile_by_user_id: Optional[dict[str, dict[str, Any]]] = None) -> Optional[ProviderEntrant]:
    """Map a raw start.gg entrant node to ProviderEntrant."""
    if not raw:
        return None
    parts = raw.get("participants", []) or []
    prefix, gamertag, cfn = _extract_profile_fields(parts, profile_by_user_id)
    country = _extract_country(parts, profile_by_user_id)
    return ProviderEntrant(
        id=str(raw["id"]),
        name=raw.get("name", "TBD"),
        avatar_url=_extract_avatar(parts),
        user_id=_extract_user_id(parts),
        prefix=prefix,
        gamertag=gamertag,
        cfn=cfn,
        country=country,
    )


def is_preview_set(raw: Dict[str, Any]) -> bool:
    """Preview sets (unresolved upstream) have non-numeric IDs like 'preview_xxx'
    and reject all mutations. Callers should filter them out before reporting."""
    sid = str(raw.get("id", ""))
    return sid.startswith("preview")


def map_set(raw: Dict[str, Any], event_id: str = "", event_name: str = "") -> ProviderSet:
    """Map a raw start.gg set node to ProviderSet.

    `event_id`/`event_name` are supplied by the caller (the provider iterates
    events when paginating sets) so each set knows which event it belongs to.
    """
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
        event_id=str(event_id or ""),
        event_name=event_name or "",
        provider_set_id=str(raw["id"]),
        # Keep the upstream ActivityState separate from the canonical
        # ProviderSetState enum so API consumers can diagnose either axis.
        provider_state_raw=str(state_int) if state_int is not None else None,
        provider_updated_at=raw.get("completedAt"),
        winner_id=str(raw["winnerId"]) if raw.get("winnerId") is not None else None,
    )


def map_tournament(raw: Dict[str, Any]) -> ProviderTournament:
    """Map a raw start.gg tournament response to ProviderTournament."""
    profile_by_user_id: dict[str, dict[str, Any]] = {}
    for participant in ((raw.get("participants") or {}).get("nodes") or []):
        if not isinstance(participant, dict):
            continue
        user = participant.get("user") if isinstance(participant.get("user"), dict) else {}
        if user.get("id") is not None:
            profile_by_user_id[str(user["id"])] = participant
    events = []
    for ev in raw.get("events", []):
        entrants = [
            map_entrant(n, profile_by_user_id)
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
    starts_at = raw.get("startAt") or raw.get("starts_at")
    # Start.gg exposes startAt as a Unix timestamp. Keep the public contract
    # string-based while accepting already-normalized fixture values.
    if isinstance(starts_at, (int, float)):
        starts_at = datetime.fromtimestamp(starts_at, tz=UTC).isoformat()
    return ProviderTournament(
        id=str(raw.get("id", "")),
        name=raw.get("name", ""),
        events=events,
        streams=streams,
        starts_at=str(starts_at) if starts_at is not None else None,
        state=str(raw.get("state")) if raw.get("state") is not None else None,
    )
