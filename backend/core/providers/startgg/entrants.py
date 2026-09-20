"""Canonical Start.gg Event entrant projections.

The public provider model historically exposed one ``name`` field.  Registration
needs the two participant-facing values separately: ``prefix`` (team, sponsor,
or clan prefix) and ``gamertag`` (the competitive player name).  This module is
the only place where Start.gg's nested participant shape is interpreted for
that purpose.  It is intentionally read-only and safe to use with fixture
payloads or an injected client.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


EVENT_ENTRANTS_QUERY = """
query RegistrationEventEntrants($slug: String!, $page: Int!, $perPage: Int!) {
  event(slug: $slug) {
    id
    slug
    entrants(query: {page: $page, perPage: $perPage}) {
      nodes {
        id
        name
        participants {
          gamerTag
          prefix
          connectedAccounts
          player { prefix gamerTag }
          user { id images { url type } }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class StartGGEntrant:
    """Safe, provider-neutral entrant facts used by registration sync."""

    provider_entrant_id: str
    provider_user_id: str | None
    prefix: str | None
    gamertag: str
    display_name: str
    avatar_url: str | None = None
    cfn: str | None = None

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


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _participant_player(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    participants = raw.get("participants")
    if isinstance(participants, list):
        for participant in participants:
            if not isinstance(participant, Mapping):
                continue
            player = _first_mapping(
                participant.get("player"),
                participant.get("user", {}).get("player")
                if isinstance(participant.get("user"), Mapping)
                else None,
            )
            if player:
                return player
    return _first_mapping(raw.get("player"), raw.get("user"))


def _avatar(raw: Mapping[str, Any], player: Mapping[str, Any], user: Mapping[str, Any]) -> str | None:
    direct = _text(raw.get("avatar_url") or raw.get("avatarUrl"))
    if direct:
        return direct
    images = player.get("images") or user.get("images") or raw.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, Mapping) and _text(image.get("url")):
                return _text(image.get("url"))
    return None


def map_entrant(raw: Mapping[str, Any] | None) -> StartGGEntrant | None:
    """Map a raw Start.gg entrant node into canonical registration fields."""

    if not isinstance(raw, Mapping) or raw.get("id") is None:
        return None
    participant = {}
    participants = raw.get("participants")
    if isinstance(participants, list) and participants and isinstance(participants[0], Mapping):
        participant = participants[0]
    user = participant.get("user") if isinstance(participant.get("user"), Mapping) else {}
    player = _participant_player(raw)
    name = _text(raw.get("name")) or _text(player.get("gamerTag") or player.get("gamertag")) or f"Entrant {raw['id']}"
    prefix = _text(raw.get("prefix")) or _text(participant.get("prefix")) or _text(player.get("prefix"))
    gamertag = (
        _text(raw.get("gamertag") or raw.get("gamerTag"))
        or _text(participant.get("gamerTag") or participant.get("gamertag"))
        or _text(player.get("gamerTag") or player.get("gamertag"))
    )
    provider_user_id = _text(
        raw.get("provider_user_id")
        or raw.get("user_id")
        or user.get("id")
        or player.get("userId")
        or player.get("user_id")
    )
    accounts = participant.get("connectedAccounts") if isinstance(participant, Mapping) else None
    capcom = accounts.get("capcom") if isinstance(accounts, Mapping) else None
    cfn = _text(capcom.get("value") or capcom.get("id")) if isinstance(capcom, Mapping) else None
    return StartGGEntrant(
        provider_entrant_id=str(raw["id"]),
        provider_user_id=provider_user_id,
        prefix=prefix,
        gamertag=gamertag,
        display_name=name,
        avatar_url=_avatar(raw, player, user),
        cfn=cfn,
    )


def map_event_entrants(raw_event: Mapping[str, Any] | None) -> list[StartGGEntrant]:
    """Map exactly one Event's entrant page; no tournament-wide scanning."""

    if not isinstance(raw_event, Mapping):
        return []
    raw_entrants = raw_event.get("entrants")
    if isinstance(raw_entrants, Mapping):
        raw_entrants = raw_entrants.get("nodes") or []
    return [mapped for item in (raw_entrants or []) if (mapped := map_entrant(item))]


async def fetch_event_entrants(client: Any, event_slug: str, *, per_page: int = 250) -> list[StartGGEntrant]:
    """Fetch entrant pages for one exact Start.gg Event scope.

    The caller supplies the already account-bound client.  Pagination remains
    bounded and provider raw response objects never leave this module.
    """

    slug = str(event_slug or "").strip()
    if not slug:
        raise ValueError("event_slug_required")
    page = 1
    result: list[StartGGEntrant] = []
    while page <= 100:
        payload = await client.query(EVENT_ENTRANTS_QUERY, {"slug": slug, "page": page, "perPage": max(1, min(int(per_page), 250))})
        event = payload.get("event") if isinstance(payload, Mapping) else None
        current = map_event_entrants(event)
        result.extend(current)
        page_info = ((event or {}).get("entrants") or {}).get("pageInfo") if isinstance(event, Mapping) else None
        if not current or not isinstance(page_info, Mapping) or not page_info.get("hasNextPage"):
            break
        page += 1
    return result


class StartGGEntrantReader:
    def __init__(self, client: Any):
        self.client = client

    async def fetch_event_entrants(self, event_slug: str, *, per_page: int = 250) -> list[StartGGEntrant]:
        return await fetch_event_entrants(self.client, event_slug, per_page=per_page)


# Explicit aliases make adapter call sites self-documenting and preserve a
# stable import surface for future provider implementations.
map_startgg_entrant = map_entrant
map_startgg_event_entrants = map_event_entrants
fetch_exact_event_roster = fetch_event_entrants


__all__ = [
    "StartGGEntrant",
    "map_entrant",
    "map_event_entrants",
    "map_startgg_entrant",
    "map_startgg_event_entrants",
    "fetch_event_entrants",
    "StartGGEntrantReader",
    "fetch_exact_event_roster",
]
