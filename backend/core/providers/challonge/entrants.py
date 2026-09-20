"""Canonical Challonge bracket participant projections."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ChallongeEntrant:
    provider_entrant_id: str
    provider_user_id: str | None
    prefix: str | None
    gamertag: str
    display_name: str
    avatar_url: str | None = None

    @property
    def entrant_id(self) -> str:
        return self.provider_entrant_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _attrs(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    value = raw.get("attributes")
    return value if isinstance(value, Mapping) else raw


def _split_display_name(value: str) -> tuple[str | None, str]:
    display = str(value or "").strip()
    for separator in ("|", " • ", " / "):
        if separator in display:
            left, right = (part.strip() for part in display.split(separator, 1))
            if left and right:
                return left, right
    return None, display


def map_entrant(raw: Mapping[str, Any] | None) -> ChallongeEntrant | None:
    """Map one Challonge JSON:API participant without merging prefix/tag."""

    if not isinstance(raw, Mapping) or raw.get("id") is None:
        return None
    attrs = _attrs(raw)
    name = _text(attrs.get("name") or attrs.get("display_name")) or f"Entrant {raw['id']}"
    parsed_prefix, parsed_gamertag = _split_display_name(name)
    prefix = _text(attrs.get("prefix") or attrs.get("team") or attrs.get("clan")) or parsed_prefix
    gamertag = _text(attrs.get("gamertag") or attrs.get("gamer_tag") or attrs.get("gamerTag")) or parsed_gamertag
    return ChallongeEntrant(
        provider_entrant_id=str(raw["id"]),
        provider_user_id=_text(attrs.get("user_id") or attrs.get("player_id")),
        prefix=prefix,
        gamertag=gamertag,
        display_name=name,
        avatar_url=_text(attrs.get("avatar_url") or attrs.get("image_url")),
    )


def map_bracket_entrants(raw_participants: list[Mapping[str, Any]] | None) -> list[ChallongeEntrant]:
    """Map only the participants returned for the selected bracket."""

    return [mapped for item in (raw_participants or []) if (mapped := map_entrant(item))]


async def fetch_bracket_entrants(client: Any, tournament_id: str, community_id: str | None = None) -> list[ChallongeEntrant]:
    """Fetch participants for one exact Challonge bracket."""

    identifier = str(tournament_id or "").strip()
    if not identifier:
        raise ValueError("tournament_id_required")
    participants = await client.participants(identifier, community_id)
    return map_bracket_entrants(participants if isinstance(participants, list) else [])


class ChallongeEntrantReader:
    def __init__(self, client: Any):
        self.client = client

    async def fetch_bracket_entrants(self, tournament_id: str, community_id: str | None = None) -> list[ChallongeEntrant]:
        return await fetch_bracket_entrants(self.client, tournament_id, community_id)


map_challonge_entrant = map_entrant
map_challonge_bracket_entrants = map_bracket_entrants
fetch_exact_bracket_roster = fetch_bracket_entrants


__all__ = [
    "ChallongeEntrant",
    "map_entrant",
    "map_bracket_entrants",
    "map_challonge_entrant",
    "map_challonge_bracket_entrants",
    "fetch_bracket_entrants",
    "ChallongeEntrantReader",
    "fetch_exact_bracket_roster",
]
