"""Read-only Challonge bracket resolver used by the setup wizard."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from backend.core.provider_discovery import LocatorKind, ProviderDiscoveryError, ProviderLocator
from backend.core.providers.challonge.client import ChallongeClient


def _attrs(item: Mapping[str, Any]) -> Mapping[str, Any]:
    value = item.get("attributes")
    return value if isinstance(value, Mapping) else {}


class ChallongeDiscovery:
    """Resolve a numeric ID or slug as one explicit managed bracket."""

    def __init__(self, client: ChallongeClient | None = None):
        self.client = client

    async def discover(self, locator: ProviderLocator, *, account_id: str) -> Mapping[str, Any]:
        if locator.provider != "challonge" or locator.kind is not LocatorKind.BRACKET:
            raise ProviderDiscoveryError("invalid_locator", "This locator does not belong to Challonge.")
        client = self.client or ChallongeClient(account_id=account_id)
        try:
            raw = await client.get_tournament(locator.tournament_slug, locator.community)
        finally:
            if self.client is None:
                await client.close()
        if not isinstance(raw, Mapping) or not raw.get("id"):
            raise ProviderDiscoveryError("scope_not_found", "The Challonge bracket was not found or is not accessible.", status_code=404)
        attrs = _attrs(raw)
        external_id = str(raw.get("id"))
        observed_at = datetime.now(UTC).isoformat()
        name = attrs.get("name") or f"Challonge {external_id}"
        scope = {
            "kind": "bracket",
            "external_id": external_id,
            "canonical_slug": attrs.get("url") or attrs.get("url_slug") or locator.tournament_slug,
            "name": name,
            "game": attrs.get("game_name"),
            "format": attrs.get("tournament_type"),
            "state": attrs.get("state"),
        }
        return {
            "tournament": {
                "external_id": external_id,
                "canonical_slug": attrs.get("url") or attrs.get("url_slug") or locator.tournament_slug,
                "name": name,
                "starts_at": attrs.get("starts_at"),
                "timezone": attrs.get("timezone"),
                "state": attrs.get("state"),
                "logo_url": attrs.get("image_url") or attrs.get("logo_url"),
            },
            "scopes": [scope],
            "selected_scope_id": external_id,
            "observed_at": observed_at,
            "start_in_wave_state": "unsupported",
        }


__all__ = ["ChallongeDiscovery"]
