from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List
from backend.core.contracts.tournament_types import (
    ProviderTournament, ProviderSet, ProviderSetState, ProviderSetResult,
    ProviderStream,
)

class ITournamentProvider(ABC):
    """Abstract interface for tournament bracket providers.
    
    Implementations:
      - StartGGProvider  (start.gg GraphQL API)
      - ChallongeProvider (future)
      - ManualProvider   (future — no external API, hub-only)
    
    Design Contracts:
      1. All methods return provider-agnostic dataclasses.
      2. Methods must NOT write to the database or broadcast WebSocket events.
      3. Errors should be raised as exceptions, not returned as None/False.
      4. Implementations must handle their own rate limiting internally.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name, e.g. 'start.gg', 'Challonge'."""
        ...

    # ── Queries ────────────────────────────────────────────────────────

    @abstractmethod
    async def fetch_tournament(self, slug_or_id: str) -> Optional[ProviderTournament]:
        """Fetch tournament metadata including events and entrants.
        
        Args:
            slug_or_id: Provider-specific identifier (slug for start.gg, ID for Challonge)
        
        Returns:
            ProviderTournament or None if not found.
        """
        ...

    @abstractmethod
    async def fetch_sets(self, slug_or_id: str) -> List[ProviderSet]:
        """Fetch all bracket sets for a tournament.
        
        Must handle pagination internally and return the complete list.
        
        Args:
            slug_or_id: Tournament identifier.
        
        Returns:
            List of all sets in provider-agnostic format.
        """
        ...

    @abstractmethod
    async def fetch_set_state(self, set_id: str) -> Optional[ProviderSetState]:
        """Fetch current state of a single set."""
        ...

    @abstractmethod
    async def fetch_set_entrant_order(self, set_id: str) -> List[str]:
        """Fetch the canonical slot ordering of entrants for a set.
        
        Returns:
            List of entrant IDs in slot order [entrant1, entrant2].
        """
        ...

    # ── Mutations ──────────────────────────────────────────────────────

    @abstractmethod
    async def report_score(
        self,
        set_id: str,
        winner_id: str,
        entrant1_id: str,
        entrant2_id: str,
        entrant1_score: int,
        entrant2_score: int,
    ) -> ProviderSetResult:
        """Report match scores with per-game data.
        
        Implementations should handle internal prerequisites 
        (e.g., marking in-progress on start.gg).
        """
        ...

    @abstractmethod
    async def report_winner_only(self, set_id: str, winner_id: str) -> ProviderSetResult:
        """Report only the winner (no score details). Fallback for score report failures."""
        ...

    @abstractmethod
    async def mark_in_progress(self, set_id: str) -> ProviderSetResult:
        """Mark a set as in-progress on the provider."""
        ...

    @abstractmethod
    async def mark_dq(self, set_id: str, winner_id: str) -> ProviderSetResult:
        """DQ the opponent and advance the winner."""
        ...

    @abstractmethod
    async def reset_set(self, set_id: str) -> ProviderSetResult:
        """Reset a completed set to its initial state."""
        ...

    async def mark_double_dq(
        self, set_id: str, entrant1_id: str, entrant2_id: str
    ) -> ProviderSetResult:
        """Resolve a set where BOTH entrants are disqualified (double no-show).

        Optional capability. Providers that cannot represent a double DQ should
        leave this default, which reports failure so callers can fall back to a
        local-only resolution. Implementations must resolve the set so the
        bracket does not stall.
        """
        return ProviderSetResult(
            success=False, set_id=set_id,
            error_message="Provider does not support double DQ."
        )

    # ── Streams (optional capability) ──────────────────────────────────
    # Providers that don't support streams can return [] from fetch_streams
    # and a failed ProviderSetResult from assign_stream / remove_stream.
    # Callers must treat all three as best-effort and never block on them.

    async def fetch_streams(self, slug_or_id: str) -> List[ProviderStream]:
        """Fetch streams configured on the tournament. Default: no streams."""
        return []

    async def assign_stream(self, set_id: str, stream_id: str) -> ProviderSetResult:
        """Push a set onto the provider's public stream queue. Default: no-op failure."""
        return ProviderSetResult(
            success=False, set_id=set_id,
            error_message="Provider does not support stream queues."
        )

    async def remove_stream(self, set_id: str) -> ProviderSetResult:
        """Remove a set from the provider's public stream queue. Default: no-op failure."""
        return ProviderSetResult(
            success=False, set_id=set_id,
            error_message="Provider does not support stream queues."
        )

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def close(self) -> None:
        """Cleanup resources (HTTP clients, connections). Called on shutdown."""
        pass
