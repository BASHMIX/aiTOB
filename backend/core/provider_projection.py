"""Non-secret provider identity and capability projections for Hub APIs.

This is intentionally local metadata: reading it never performs provider I/O and
does not expose credentials, tokens, or raw request data.
"""
from __future__ import annotations

from backend.core.contracts import ITournamentProvider, ITournamentProviderV2


def provider_capability_projection(provider: ITournamentProvider) -> dict:
    if not isinstance(provider, ITournamentProviderV2):
        return {"contract_version": "legacy", "actions": []}
    return {
        "contract_version": "v2",
        "actions": [
            {
                "action": action,
                "availability": capability.kind.value,
                "reason": capability.reason,
            }
            for action, capability in sorted(provider.capabilities_v2.actions.items())
        ],
        "supports_incremental_sync": provider.capabilities_v2.supports_incremental_sync,
        "supports_targeted_match_fetch": provider.capabilities_v2.supports_targeted_match_fetch,
        "supports_remote_revision": provider.capabilities_v2.supports_remote_revision,
        "supports_idempotency": provider.capabilities_v2.supports_idempotency,
    }


def tournament_provider_projection(tournament: dict, provider: ITournamentProvider) -> dict:
    provider_type = tournament.get("provider_type") or getattr(provider, "provider_type", "startgg")
    return {
        "provider_type": provider_type,
        "display_name": provider.provider_name,
        "provider_tournament_id": tournament.get("provider_tournament_id"),
        "provider_subdomain": tournament.get("provider_subdomain"),
        **provider_capability_projection(provider),
    }


def reviewed_identity_projection(tournament: dict, provider_facts: dict | None = None, local_brand: dict | None = None) -> dict:
    """Project one canonical identity to Hub, Editor and overlay consumers."""
    from backend.core.tournament_brand import project_tournament_brand
    brand = project_tournament_brand(provider_facts or {}, local_brand or {}, logo_url=tournament.get("logo_url"))
    value = brand.as_dict()
    value.update({"tournament_id": tournament.get("slug") or tournament.get("id"), "provider_type": tournament.get("provider_type"), "event_id": tournament.get("event_id")})
    return value


project_reviewed_identity = reviewed_identity_projection
