"""Read-only Start.gg tournament/Event resolver used by the setup wizard."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from backend.core.provider_discovery import (
    LocatorKind,
    ProviderDiscoveryError,
    ProviderLocator,
)
from backend.core.providers.startgg import queries
from backend.core.providers.startgg.client import StartGGClient


def _image_url(images: Any) -> str | None:
    if not isinstance(images, list):
        return None
    for image in images:
        if isinstance(image, Mapping) and image.get("url"):
            return str(image["url"])
    return None


def _safe_tournament(raw: Mapping[str, Any], fallback_slug: str) -> dict[str, Any]:
    """Project provider facts only; raw GraphQL data never crosses the boundary."""

    return {
        "external_id": str(raw.get("id") or ""),
        "canonical_slug": raw.get("slug") or fallback_slug,
        "name": raw.get("name"),
        "starts_at": raw.get("startAt") or raw.get("starts_at"),
        "timezone": raw.get("timezone"),
        "state": raw.get("state"),
        "logo_url": _image_url(raw.get("images")),
    }


def _safe_scope(raw: Mapping[str, Any], fallback_slug: str | None = None) -> dict[str, Any]:
    game = raw.get("videogame")
    return {
        "kind": "event",
        "external_id": str(raw.get("id") or ""),
        "canonical_slug": raw.get("slug") or fallback_slug,
        "name": raw.get("name"),
        "game": game.get("name") if isinstance(game, Mapping) else game,
        "format": raw.get("format") or raw.get("bracketType"),
        "state": raw.get("state"),
    }


class StartGGDiscovery:
    """Resolve one exact Start.gg scope with the account selected by the draft."""

    def __init__(self, client: StartGGClient | None = None):
        self.client = client

    async def _query(self, account_id: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        client = self.client or StartGGClient(provider_account_id=account_id)
        try:
            result = await client.query(query, variables)
            return result if isinstance(result, dict) else {}
        finally:
            # Injected clients are owned by tests/callers; a locally-created
            # client must release its HTTP connection after read-only preview.
            if self.client is None:
                await client.close()

    async def discover(self, locator: ProviderLocator, *, account_id: str) -> Mapping[str, Any]:
        if locator.provider != "startgg":
            raise ProviderDiscoveryError("invalid_locator", "This locator does not belong to Start.gg.")
        observed_at = datetime.now(UTC).isoformat()
        if locator.kind is LocatorKind.EVENT:
            data = await self._query(account_id, queries.EVENT_INFO, {"slug": locator.scope_slug or locator.tournament_slug})
            raw_event = data.get("event") if isinstance(data, Mapping) else None
            if not isinstance(raw_event, Mapping) or not raw_event.get("id"):
                raise ProviderDiscoveryError("scope_not_found", "The Start.gg Event was not found or is not accessible.", status_code=404)
            parent = raw_event.get("tournament")
            if not isinstance(parent, Mapping) or not parent.get("id"):
                raise ProviderDiscoveryError("scope_not_found", "The Start.gg Event has no accessible parent tournament.", status_code=404)
            scope = _safe_scope(raw_event, locator.scope_slug)
            if not scope["external_id"]:
                raise ProviderDiscoveryError("scope_not_found", "The Start.gg Event did not return an identity.", status_code=404)
            return {
                "tournament": _safe_tournament(parent, locator.tournament_slug),
                "scopes": [scope],
                "selected_scope_id": scope["external_id"],
                "observed_at": observed_at,
                "start_in_wave_state": "unknown",
            }

        data = await self._query(account_id, queries.TOURNAMENT_INFO, {"slug": locator.tournament_slug})
        raw_tournament = data.get("tournament") if isinstance(data, Mapping) else None
        if not isinstance(raw_tournament, Mapping) or not raw_tournament.get("id"):
            raise ProviderDiscoveryError("scope_not_found", "The Start.gg tournament was not found or is not accessible.", status_code=404)
        scopes = [
            _safe_scope(event)
            for event in (raw_tournament.get("events") or [])
            if isinstance(event, Mapping) and event.get("id")
        ]
        # ``discover`` deliberately leaves selected_scope_id unset for more
        # than one event.  The neutral resolver chooses the sole event only.
        return {
            "tournament": _safe_tournament(raw_tournament, locator.tournament_slug),
            "scopes": scopes,
            "observed_at": observed_at,
            "start_in_wave_state": "unknown",
        }


__all__ = ["StartGGDiscovery"]
