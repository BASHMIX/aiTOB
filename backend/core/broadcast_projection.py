"""Shared, read-only broadcast state for the Editor and OBS viewer."""

from __future__ import annotations

import json
from typing import Any

from backend.core import database


def apply_tournament_entrant_metadata(match: dict, tournament: dict | None) -> dict:
    """Fill missing broadcast identity fields from saved provider metadata.

    The active-set feed can omit profile fields even though the tournament
    metadata response contains them.  Prefer the set row when it has a value,
    then fall back to the exact entrant stored in the selected tournament.
    Organizer overrides are applied after this function and therefore remain
    authoritative.
    """
    projected = dict(match)
    try:
        raw = json.loads((tournament or {}).get("raw_data") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        raw = {}

    events = raw.get("events") or (raw.get("tournament") or {}).get("events") or []
    event_id = str(projected.get("event_id") or "")
    if event_id:
        scoped_events = [event for event in events if str(event.get("id") or "") == event_id]
        if scoped_events:
            events = scoped_events

    entrants: dict[str, dict[str, Any]] = {}
    for event in events:
        for entrant in ((event.get("entrants") or {}).get("nodes") or []):
            if isinstance(entrant, dict) and entrant.get("id") is not None:
                entrants.setdefault(str(entrant["id"]), entrant)

    for slot in ("p1", "p2"):
        entrant_id = str(projected.get(f"{slot}_entrant_id") or "")
        entrant = entrants.get(entrant_id)
        if not entrant:
            continue

        participants = entrant.get("participants") or []
        participant = next((item for item in participants if isinstance(item, dict)), {})
        user = participant.get("user") if isinstance(participant.get("user"), dict) else {}
        location = user.get("location") if isinstance(user.get("location"), dict) else {}
        accounts = participant.get("connectedAccounts") or {}
        capcom = accounts.get("capcom") if isinstance(accounts, dict) else None

        prefix = entrant.get("prefix") or participant.get("prefix")
        country = entrant.get("country") or location.get("country")
        cfn = entrant.get("cfn")
        if not cfn and isinstance(capcom, dict):
            cfn = capcom.get("value") or capcom.get("id")

        images = user.get("images") or []
        avatar = next(
            (image.get("url") for image in images if isinstance(image, dict) and image.get("type") == "profile" and image.get("url")),
            None,
        ) or next(
            (image.get("url") for image in images if isinstance(image, dict) and image.get("url")),
            None,
        )

        for field, value in (("prefix", prefix), ("country", country), ("cfn", cfn), ("avatar", avatar)):
            key = f"{slot}_{field}"
            if projected.get(key) in (None, "") and value not in (None, ""):
                projected[key] = str(value).strip()

    return projected


async def get_station_broadcast_state(station_id: str, workspace_id: str) -> dict[str, Any] | None:
    """Return the same broadcast match projection to every trusted consumer."""
    station = await database.get_station(station_id, workspace_id)
    if not station:
        return None

    matches = await database.get_active_matches(workspace_id=workspace_id)
    storage_ids = {station_id, station.get("storage_id")}
    active_match = next(
        (
            match for match in matches
            if match.get("station_id") in storage_ids
            and str(match.get("status") or "").lower() in {"called", "ready", "in_progress"}
        ),
        None,
    )

    preview_mode = False
    preview_id = station.get("preview_match_id")
    if not active_match and preview_id:
        preview_candidate = await database.get_active_match(str(preview_id), workspace_id)
        if preview_candidate and str(preview_candidate.get("status") or "").lower() == "not_started":
            active_match = preview_candidate
            preview_mode = True
        else:
            await database.set_station_preview(station_id, None, workspace_id)
            station = await database.get_station(station_id, workspace_id) or station

    tournament_name = None
    if active_match:
        tournament = None
        tournament_slug = active_match.get("tournament_slug")
        if tournament_slug:
            tournament = await database.get_tournament(str(tournament_slug), workspace_id)
            tournament_name = (tournament or {}).get("name")

        active_match = apply_tournament_entrant_metadata(active_match, tournament)
        overrides = await database.get_all_player_overrides(workspace_id)
        active_match = database.apply_player_overrides_to_match(active_match, overrides)
        active_match = database.serialize_active_match_for_display(active_match)

        # The selected event/videogame is authoritative. Preview matches can
        # retain a stale game_name from an older mock match (e.g. TEKKEN 8),
        # so never let that value override the tournament event metadata.
        event_game_name = ""
        if tournament:
            try:
                raw = json.loads(tournament.get("raw_data") or "{}")
                events = raw.get("events") or (raw.get("tournament") or {}).get("events") or []
                event_id = str(active_match.get("event_id") or station.get("event_id") or "")
                event = next((item for item in events if str(item.get("id") or "") == event_id), None) if event_id else None
                event_game_name = str(
                    (event or {}).get("game")
                    or ((event or {}).get("videogame") or {}).get("name")
                    or ""
                )
            except (TypeError, ValueError, AttributeError, json.JSONDecodeError):
                event_game_name = ""
        active_match["game_name"] = event_game_name or str((tournament or {}).get("game") or active_match.get("game_name") or "")

    # Next match projection from the station stream queue
    from backend.core.tournament_progression import _unresolved
    queue = await database.get_station_queue(station_id, workspace_id)
    next_match = None
    next_match_tbd = True
    busy_players: list[dict] = []

    if queue:
        raw_next = dict(queue[0])
        busy_players = raw_next.get("busy_players") or []
        t_slug = raw_next.get("tournament_slug")
        next_tournament = await database.get_tournament(str(t_slug), workspace_id) if t_slug else None
        next_proj = apply_tournament_entrant_metadata(raw_next, next_tournament)
        overrides = overrides if 'overrides' in locals() else await database.get_all_player_overrides(workspace_id)
        next_proj = database.apply_player_overrides_to_match(next_proj, overrides)
        next_proj = database.serialize_active_match_for_display(next_proj)

        p1_unres = _unresolved(next_proj.get("p1_name"))
        p2_unres = _unresolved(next_proj.get("p2_name"))
        next_match_tbd = p1_unres or p2_unres

        if next_match_tbd:
            next_status = "Awaiting Opponent"
        elif busy_players:
            next_status = f"Waiting ({busy_players[0]['player']})"
        else:
            next_status = "Ready"

        next_proj["match_status"] = next_status
        next_proj["busy_players"] = busy_players
        next_match = next_proj

    return {
        "station": station,
        "active_match": active_match,
        "tournament_name": tournament_name,
        "preview_mode": preview_mode,
        "next_match": next_match,
        "next_match_tbd": next_match_tbd,
        "busy_players": busy_players,
    }
