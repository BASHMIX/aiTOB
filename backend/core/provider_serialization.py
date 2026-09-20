"""Public, provider-neutral serialization for bracket snapshots.

The canonical ``ProviderSetState`` belongs to aiTOB.  Provider adapters keep
their original state in ``provider_state_raw`` so clients can display and
diagnose both axes without guessing which numeric enum they received.
"""
from __future__ import annotations

from typing import Any

from backend.core.contracts.tournament_types import ProviderSet


def serialize_provider_set(provider_set: ProviderSet) -> dict[str, Any]:
    """Return the stable frontend snapshot shape without credentials."""
    aitob_state = provider_set.state.name.lower()
    payload = {
        "id": provider_set.id,
        # Legacy alias retained for existing consumers. This is the canonical
        # aiTOB ProviderSetState code, never a provider-specific enum.
        "state": int(provider_set.state),
        "aitob_state": aitob_state,
        "aitob_state_code": int(provider_set.state),
        "state_source": "aitob",
        "provider_set_id": provider_set.provider_set_id,
        "provider_state_raw": provider_set.provider_state_raw,
        "provider_revision": provider_set.provider_revision,
        "provider_updated_at": provider_set.provider_updated_at,
        "round": provider_set.round_name,
        "fullRoundText": provider_set.round_name,
        "identifier": provider_set.identifier,
        "event_id": provider_set.event_id,
        "event_name": provider_set.event_name,
        "phaseGroup": {"displayIdentifier": provider_set.phase_group},
        "p1": provider_set.entrant1.name if provider_set.entrant1 else "TBD",
        "p2": provider_set.entrant2.name if provider_set.entrant2 else "TBD",
        "p1_avatar": provider_set.entrant1.avatar_url if provider_set.entrant1 else None,
        "p2_avatar": provider_set.entrant2.avatar_url if provider_set.entrant2 else None,
        "p1_eid": provider_set.entrant1.id if provider_set.entrant1 else None,
        "p2_eid": provider_set.entrant2.id if provider_set.entrant2 else None,
        "winner_id": provider_set.winner_id,
        "p1_score": provider_set.entrant1_score,
        "p2_score": provider_set.entrant2_score,
    }
    # Profile facts are additive only when a slot has resolved. This preserves
    # the historical TBD serialization shape used by V2 read-gateway clients.
    for slot, entrant in (("p1", provider_set.entrant1), ("p2", provider_set.entrant2)):
        if entrant is not None:
            payload.update({
                f"{slot}_prefix": entrant.prefix,
                f"{slot}_country": entrant.country,
                f"{slot}_cfn": entrant.cfn,
            })
    return payload
