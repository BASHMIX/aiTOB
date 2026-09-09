"""Provider-safe Discord identity resolution for Hub workflow effects."""
from __future__ import annotations

from backend.core.database import get_verified_discord_identity_link_v2, upsert_provider_identity_link_v2


async def resolve_verified_discord_recipient(provider_type: str, tournament_slug: str, entrant_id: str, workspace_id: str | None = None) -> str | None:
    """Resolve by stable entrant ID only; names are never accepted as input."""
    link = await get_verified_discord_identity_link_v2(provider_type, tournament_slug, entrant_id, workspace_id)
    return str(link["discord_user_id"]) if link else None


async def save_identity_override(link: dict, workspace_id: str | None = None) -> dict:
    """Store an organizer-verified mapping without mutating a provider participant."""
    return await upsert_provider_identity_link_v2({
        **link,
        "verification_state": "organizer_override",
        "source": "organizer_override",
    }, workspace_id)
