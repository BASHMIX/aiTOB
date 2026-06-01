from __future__ import annotations
from typing import Dict, Optional
from backend.core.contracts import ITournamentProvider
from backend.core.providers.startgg import StartGGProvider

# Singleton provider instances (one per provider type)
_providers: Dict[str, ITournamentProvider] = {}


def register_provider(name: str, provider: ITournamentProvider) -> None:
    """Register a provider instance by name."""
    _providers[name] = provider


def get_provider(name: str = "startgg") -> ITournamentProvider:
    """Get a provider by name. Lazily initializes default providers."""
    if name not in _providers:
        if name == "startgg":
            _providers[name] = StartGGProvider()
        else:
            raise ValueError(f"Unknown provider: {name}. Register it first.")
    return _providers[name]


async def get_provider_for_tournament(tournament_slug: str) -> ITournamentProvider:
    """Resolve the correct provider for a tournament.
    
    Future: Reads tournament.provider_type from DB.
    Current: Always returns start.gg provider (backward compatible).
    """
    # Phase 1: Always start.gg
    # Phase 2: Add `provider_type TEXT DEFAULT 'startgg'` column to tournaments table
    #          and resolve from DB here.
    return get_provider("startgg")


async def shutdown_providers() -> None:
    """Close all provider HTTP clients. Call on app shutdown."""
    for provider in _providers.values():
        await provider.close()
    _providers.clear()
