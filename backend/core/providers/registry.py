from __future__ import annotations
from typing import Callable, Dict, Optional
import os
from backend.core.contracts import ITournamentProvider, ITournamentProviderV2

# Singleton provider instances (one per provider type)
_providers: Dict[str, ITournamentProvider] = {}

# V2 factories intentionally have a separate registry.  Nothing in the legacy
# runtime resolves them during Phase 2, so existing provider instances and routes
# retain their baseline behavior while the contracts are introduced.
_provider_v2_factories: Dict[str, Callable[[], ITournamentProviderV2]] = {}


def register_provider(name: str, provider: ITournamentProvider) -> None:
    """Register a provider instance by name."""
    _providers[name] = provider


def register_provider_v2_factory(
    provider_type: str, factory: Callable[[], ITournamentProviderV2]
) -> None:
    """Register a dark V2 adapter factory without constructing an HTTP client."""
    _provider_v2_factories[provider_type] = factory


def get_provider_v2_factory(
    provider_type: str,
) -> Callable[[], ITournamentProviderV2] | None:
    """Return a V2 factory only; Phase 2 deliberately has no runtime consumer."""
    return _provider_v2_factories.get(provider_type)


def get_provider(name: str = "startgg") -> ITournamentProvider:
    """Get a provider by name. Lazily initializes default providers."""
    if name not in _providers:
        if name == "startgg":
            # Keep a Start.gg-only runtime from importing or constructing any
            # Challonge component. The old lazy-provider behavior is preserved.
            from backend.core.providers.startgg import StartGGProvider
            _providers[name] = StartGGProvider()
        elif name == "challonge":
            from backend.core.providers.challonge import ChallongeProvider
            # Legacy callers must bind an imported tournament before reaching this
            # point.  The default singleton cannot own an account credential.
            _providers[name] = ChallongeProvider(provider_account_id="unbound")
        else:
            raise ValueError(f"Unknown provider: {name}. Register it first.")
    return _providers[name]


async def get_provider_for_tournament(tournament_slug: str, workspace_id: str | None = None) -> ITournamentProvider:
    """Resolve the correct provider for a tournament.
    
    Future: Reads tournament.provider_type from DB.
    Current: Always returns start.gg provider (backward compatible).
    """
    from backend.core.database import get_tournament
    tournament = await get_tournament(tournament_slug, workspace_id)
    provider_type = (tournament or {}).get("provider_type") or "startgg"
    if provider_type != "challonge":
        account_id = str((tournament or {}).get("provider_account_id") or "")
        if provider_type == "startgg" and account_id:
            from backend.core.providers.startgg import StartGGProvider
            return StartGGProvider(provider_account_id=account_id)
        if provider_type == "startgg" and workspace_id is not None:
            # A tenant-owned tournament must never silently fall back to the
            # historical platform Start.gg credential bucket.  Unscoped
            # callers remain available for migration/test fixtures only.
            raise ValueError("Start.gg tournament is not bound to an integration account.")
        if provider_type == "startgg" and os.getenv("AITOB_LEGACY_PROVIDER_FALLBACK", "false").lower() not in {"1", "true", "yes", "on"}:
            # Unscoped resolution is retained only for explicit migration and
            # test tools. Runtime callers must pass a workspace-owned account;
            # otherwise the historical platform credential would be a silent
            # cross-tenant fallback.
            if os.getenv("AITOB_TESTING") != "1" and os.getenv("AITOB_SQLITE_MIGRATION_TOOL") != "1":
                raise ValueError("Start.gg provider workspace binding is required.")
        return get_provider(provider_type)
    account_id = str((tournament or {}).get("provider_account_id") or "")
    if not account_id:
        raise ValueError("Challonge tournament is not bound to an integration account.")
    from backend.core.providers.challonge import ChallongeProvider
    return ChallongeProvider(provider_account_id=account_id)


async def shutdown_providers() -> None:
    """Close all provider HTTP clients. Call on app shutdown."""
    for provider in _providers.values():
        await provider.close()
    _providers.clear()
